"""Team member tracker — maps analyzed comments to dashboard-ready member data.

Provides :class:`TeamMemberTracker` which:
- Loads active team member UIDs from the Account table.
- Matches pre-analyzed CommentDTO list against team UIDs.
- Produces per-member tracking data (best-ranked comment, status).
- Generates a 20-card grid for the dashboard UI.

Design notes
------------
- Uses the output of :class:`~app.services.hot_analyzer.HotCommentAnalyzer.analyze`
  as input — comments already have ``rank``, ``is_hot``, ``is_team_member`` set.
- DB session is optional.  Without it, ``get_team_uids`` returns ``[]`` and
  ``_get_account_info`` returns unknown values.
- ``track_comments`` returns a dict keyed by UID for O(1) lookup.
- ``get_member_grid_data`` always returns exactly 20 entries (padded or truncated).
"""

from __future__ import annotations

from typing import Any

from app.schemas.comment import CommentDTO


class TeamMemberTracker:
    """Track team member comment performance and produce dashboard grid data.

    Parameters
    ----------
    db_session
        Optional SQLAlchemy session for loading Account table data.
        When ``None``, DB-dependent methods return empty/unknown results.
    """

    def __init__(self, db_session: Any = None) -> None:
        self.db_session = db_session

    # ------------------------------------------------------------------
    # Team UID loading
    # ------------------------------------------------------------------

    def get_team_uids(self) -> list[str]:
        """Load all active account ``weibo_uid`` values from the Account table.

        Returns
        -------
        list[str]
            UIDs of accounts with ``status="active"``.  Empty list when no
            DB session or no active accounts.
        """
        if self.db_session is None:
            return []

        from app.models.account import Account

        accounts = (
            self.db_session.query(Account)
            .filter(Account.status == "active")
            .all()
        )
        return [acc.weibo_uid for acc in accounts]

    # ------------------------------------------------------------------
    # Comment tracking
    # ------------------------------------------------------------------

    def track_comments(
        self,
        comments: list[CommentDTO],
        team_uids: list[str],
    ) -> dict[str, dict]:
        """Match analyzed comments against team UIDs.

        For each team member, finds their best-ranked comment (lowest rank
        number) and returns tracking data.

        Parameters
        ----------
        comments
            Pre-analyzed CommentDTO list (output of
            :meth:`HotCommentAnalyzer.analyze`).
        team_uids
            List of team member UIDs to track.

        Returns
        -------
        dict[str, dict]
            Keyed by UID.  Each value has keys: ``nickname``, ``comment_id``,
            ``rank``, ``like_count``, ``is_hot``, ``content``, ``status``,
            ``comment_count``.
            Members with a comment get ``status="has_comment"``; members
            without get ``status="no_comment"`` with ``None`` values.
        """
        team_set = set(team_uids)

        # Group comments by user_uid, tracking best (lowest rank) and count.
        best_by_uid: dict[str, CommentDTO] = {}
        count_by_uid: dict[str, int] = {}

        for comment in comments:
            uid = comment.user_uid
            if uid not in team_set:
                continue

            count_by_uid[uid] = count_by_uid.get(uid, 0) + 1

            existing = best_by_uid.get(uid)
            if existing is None or comment.rank < existing.rank:
                best_by_uid[uid] = comment

        result: dict[str, dict] = {}
        for uid in team_uids:
            comment = best_by_uid.get(uid)
            if comment is not None:
                result[uid] = {
                    "nickname": comment.user_name,
                    "comment_id": comment.weibo_comment_id,
                    "rank": comment.rank,
                    "like_count": comment.like_count,
                    "is_hot": comment.is_hot,
                    "content": comment.content,
                    "status": "has_comment",
                    "comment_count": count_by_uid[uid],
                }
            else:
                result[uid] = {
                    "nickname": None,
                    "comment_id": None,
                    "rank": None,
                    "like_count": None,
                    "is_hot": False,
                    "content": None,
                    "status": "no_comment",
                    "comment_count": 0,
                }

        return result

    # ------------------------------------------------------------------
    # Dashboard grid
    # ------------------------------------------------------------------

    def get_member_grid_data(
        self,
        team_uids: list[str],
        tracked: dict[str, dict],
    ) -> list[dict]:
        """Return 20 member status cards for the dashboard grid.

        Each card contains: ``uid``, ``nickname``, ``avatar_url``,
        ``current_rank``, ``like_count``, ``is_hot``, ``comment_count``,
        ``online_status``.

        Parameters
        ----------
        team_uids
            List of team member UIDs (order preserved, max 20 used).
        tracked
            Output of :meth:`track_comments` — per-UID tracking data.

        Returns
        -------
        list[dict]
            Exactly 20 card dicts.  Padded with empty slots if fewer than
            20 members; truncated if more.
        """
        cards: list[dict] = []

        for uid in team_uids[:20]:
            tracked_info = tracked.get(uid, {})
            account_info = self._get_account_info(uid)

            # Prefer account nickname; fall back to tracked nickname (from comment).
            nickname = account_info["nickname"] or tracked_info.get("nickname")

            account_status = account_info["status"]
            online_status = "online" if account_status == "active" else "offline"

            card = {
                "uid": uid,
                "nickname": nickname,
                "avatar_url": account_info["avatar_url"],
                "current_rank": tracked_info.get("rank"),
                "like_count": tracked_info.get("like_count"),
                "is_hot": tracked_info.get("is_hot", False),
                "comment_count": tracked_info.get("comment_count", 0),
                "online_status": online_status,
            }
            cards.append(card)

        # Pad to 20 entries with empty slots.
        empty_slot: dict = {
            "uid": None,
            "nickname": None,
            "avatar_url": None,
            "current_rank": None,
            "like_count": None,
            "is_hot": False,
            "comment_count": 0,
            "online_status": "offline",
        }
        while len(cards) < 20:
            cards.append(dict(empty_slot))

        return cards

    # ------------------------------------------------------------------
    # Account helper
    # ------------------------------------------------------------------

    def _get_account_info(self, uid: str) -> dict:
        """Query the Account table for the given UID.

        Parameters
        ----------
        uid
            Weibo UID to look up.

        Returns
        -------
        dict
            ``{nickname, avatar_url, status}`` when found, or
            ``{nickname: None, avatar_url: None, status: "unknown"}`` when
            not found or no DB session.
        """
        if self.db_session is None:
            return {"nickname": None, "avatar_url": None, "status": "unknown"}

        from app.models.account import Account

        account = (
            self.db_session.query(Account)
            .filter(Account.weibo_uid == uid)
            .first()
        )
        if account is None:
            return {"nickname": None, "avatar_url": None, "status": "unknown"}

        return {
            "nickname": account.nickname,
            "avatar_url": account.avatar_url,
            "status": account.status,
        }
