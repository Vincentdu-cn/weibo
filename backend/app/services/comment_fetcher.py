"""Comment fetcher — paginated Weibo comment retrieval via buildComments API.

Provides :class:`CommentFetcher` which:
- Converts Weibo URLs to mids (base62 decoding, ref: nghuyong/WeiboSpider).
- Fetches comments from ``/ajax/statuses/buildComments`` with pagination.
- Builds :class:`~app.schemas.comment.CommentDTO` objects with rank/hot flags.
- Optionally persists comment snapshots to the database.

Design notes
------------
- ``flow=0`` means hot-comment sort order (most liked first).
- Pagination uses ``max_id`` from the API response; stops when ``max_id == 0``
  or ``max_pages`` is reached.
- Anti-detection delays are applied **between** page requests via
  :meth:`AntiDetectionEngine.wait_monitor`.
- Only first-level comments are fetched (no sub-comment / reply chains).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from app.models.comment import Comment
from app.models.comment_snapshot import CommentSnapshot
from app.schemas.comment import CommentDTO
from app.services.anti_detection import AntiDetectionEngine
from app.services.weibo_client import WeiboHttpClient

# Base62 alphabet — same as nghuyong/WeiboSpider.
_BASE62_ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"

# BuildComments endpoint path.
_COMMENTS_PATH = "/ajax/statuses/buildComments"

# Weibo date format: "Thu Jun 25 10:00:00 +0800 2025"
_WEIBO_DATE_FORMAT = "%a %b %d %H:%M:%S %z %Y"


# ---------------------------------------------------------------------------
# Base62 helpers
# ---------------------------------------------------------------------------

def _base62_decode(string: str) -> int:
    """Decode a base62 *string* to an integer.

    Uses the same alphabet as WeiboSpider:
    ``0-9 a-z A-Z`` → indices 0-61.
    """
    num = 0
    length = len(string)
    for idx, char in enumerate(string):
        power = length - (idx + 1)
        num += _BASE62_ALPHABET.index(char) * (62 ** power)
    return num


def _url_to_mid(base62: str) -> str:
    """Convert a base62 string to a Weibo mid string.

    Algorithm (ref: nghuyong/WeiboSpider ``reverse_cut_to_length``):
    1. Cut the string from the **right** in groups of 4.
    2. Reverse the list of groups.
    3. Base62-decode each group to an integer.
    4. For groups after the first, zero-pad to 7 digits.
    5. Concatenate and strip leading zeros.
    """
    content = str(base62)
    # Cut from right in groups of 4.
    cut_list: list[str] = []
    for i in range(len(content), 0, -4):
        start = i - 4 if i >= 4 else 0
        cut_list.append(content[start:i])
    cut_list.reverse()

    # Decode each group, padding intermediate groups to 7 digits.
    result_parts: list[str] = []
    for i, item in enumerate(cut_list):
        s = str(_base62_decode(item))
        if i > 0 and len(s) < 7:
            s = "0" * (7 - len(s)) + s
        result_parts.append(s)

    return "".join(result_parts).lstrip("0") or "0"


def _parse_weibo_time(time_str: str) -> Optional[datetime]:
    """Parse a Weibo ``created_at`` string to :class:`~datetime.datetime`.

    Returns ``None`` if parsing fails.
    """
    if not time_str:
        return None
    try:
        return datetime.strptime(time_str, _WEIBO_DATE_FORMAT)
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# CommentFetcher
# ---------------------------------------------------------------------------

class CommentFetcher:
    """Fetch Weibo comments via the buildComments API and save snapshots.

    Parameters
    ----------
    client
        :class:`WeiboHttpClient` for making HTTP requests.
    anti_detection
        :class:`AntiDetectionEngine` for cookie rotation and delays.
    db_session
        Optional SQLAlchemy session. When provided, fetched comments and
        their snapshots are persisted to the database.
    hot_threshold
        Comments with ``rank <= hot_threshold`` are marked ``is_hot=True``.
        Defaults to 50.
    """

    def __init__(
        self,
        client: WeiboHttpClient,
        anti_detection: AntiDetectionEngine,
        db_session: Any = None,
        hot_threshold: int = 50,
    ) -> None:
        self.client = client
        self.anti_detection = anti_detection
        self.db_session = db_session
        self.hot_threshold = hot_threshold

    # ------------------------------------------------------------------
    # URL → mid conversion
    # ------------------------------------------------------------------

    def get_weibo_mid(self, url: str) -> str:
        """Convert a Weibo URL or base62 string to a numeric mid string.

        Handles URLs with or without protocol, with or without ``www``,
        and with query parameters or trailing slashes.

        Examples
        --------
        >>> fetcher = CommentFetcher.__new__(CommentFetcher)
        >>> fetcher.get_weibo_mid("https://weibo.com/1234567890/z0JH2lOMb")
        '3501756485200075'
        """
        # Extract the base62 part after the last '/'.
        base62 = url.rstrip("/")
        if "/" in base62:
            base62 = base62.split("/")[-1]
        # Strip query parameters.
        if "?" in base62:
            base62 = base62.split("?")[0]
        return _url_to_mid(base62)

    # ------------------------------------------------------------------
    # Paginated comment fetch
    # ------------------------------------------------------------------

    async def fetch_comments(
        self,
        weibo_mid: str,
        cookie: str,
        max_pages: int = 5,
    ) -> list[CommentDTO]:
        """Fetch comments for a Weibo post via the buildComments API.

        Parameters
        ----------
        weibo_mid
            The Weibo mid of the target post (numeric string).
        cookie
            Cookie header string for authentication.
        max_pages
            Maximum number of pages to fetch (default 5).

        Returns
        -------
        list[CommentDTO]
            Comment DTOs ordered by rank (first comment = rank 1).
        """
        all_comments: list[CommentDTO] = []
        max_id: int = 0
        rank: int = 0

        for page in range(max_pages):
            params: dict[str, Any] = {
                "flow": 0,            # hot-comment sort order
                "is_reload": 1,
                "id": weibo_mid,
                "count": 20,
                "uid": "",             # logged-in user uid (not required for read)
                "max_id": max_id,
            }

            response = await self.client._get(
                _COMMENTS_PATH, params, cookie
            )

            data: list[dict] = response.get("data", [])
            if not data:
                break

            for item in data:
                rank += 1
                user = item.get("user", {})
                dto = CommentDTO(
                    id=0,  # DB ID — 0 until persisted
                    weibo_comment_id=str(item.get("id", "")),
                    user_uid=str(user.get("id", "")),
                    user_name=user.get("screen_name", ""),
                    content=item.get("text", ""),
                    like_count=item.get("like_counts", 0),
                    rank=rank,
                    is_hot=rank <= self.hot_threshold,
                    is_team_member=False,
                    created_at=_parse_weibo_time(item.get("created_at", "")),
                )
                all_comments.append(dto)

            max_id = response.get("max_id", 0)
            if max_id == 0:
                break

            # Anti-detection delay between pages.
            await self.anti_detection.wait_monitor()

        # Persist to database if a session is available.
        if self.db_session is not None and all_comments:
            self._save_snapshots(all_comments, weibo_mid)

        return all_comments

    # ------------------------------------------------------------------
    # Optional: deep-analysis like fetch
    # ------------------------------------------------------------------

    async def fetch_comment_likes(
        self, comment_id: str, cookie: str
    ) -> dict[str, Any]:
        """Fetch like information for a specific comment (optional).

        Currently returns a minimal dict with the ``comment_id``. This is a
        placeholder for future deep-analysis integration that would query
        per-comment like details via a dedicated API endpoint.

        Parameters
        ----------
        comment_id
            The Weibo comment ID to query.
        cookie
            Cookie header string for authentication.

        Returns
        -------
        dict
            Dictionary with at least ``comment_id`` key.
        """
        return {"comment_id": comment_id}

    # ------------------------------------------------------------------
    # DB persistence
    # ------------------------------------------------------------------

    def _save_snapshots(
        self, comments: list[CommentDTO], weibo_post_id: str
    ) -> None:
        """Save comment records and their snapshots to the database.

        For each comment DTO:
        - If a :class:`Comment` with the same ``weibo_comment_id`` exists,
          update its ``like_count``.
        - Otherwise, create a new :class:`Comment` record.
        - Always create a new :class:`CommentSnapshot` for the current state.
        """
        now = datetime.utcnow()

        for dto in comments:
            # Find or create Comment record.
            existing = (
                self.db_session.query(Comment)
                .filter_by(weibo_comment_id=dto.weibo_comment_id)
                .first()
            )

            if existing:
                comment = existing
                comment.like_count = dto.like_count
            else:
                comment = Comment(
                    weibo_comment_id=dto.weibo_comment_id,
                    weibo_post_id=weibo_post_id,
                    user_uid=dto.user_uid,
                    user_name=dto.user_name,
                    content=dto.content,
                    like_count=dto.like_count,
                    created_at=dto.created_at,
                    fetched_at=now,
                )
                self.db_session.add(comment)
                self.db_session.flush()  # assign comment.id

            # Create snapshot.
            snapshot = CommentSnapshot(
                comment_id=comment.id,
                like_count=dto.like_count,
                rank=dto.rank,
                is_hot=dto.is_hot,
                is_team_member=dto.is_team_member,
                snapshot_at=now,
            )
            self.db_session.add(snapshot)

        self.db_session.commit()
