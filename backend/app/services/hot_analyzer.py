"""Hot comment analyzer — ranking, team member tracking, and change detection.

Provides :class:`HotCommentAnalyzer` which:
- Ranks comments by a configurable field (default: ``like_count`` descending).
- Marks comments as hot based on ``top_n`` threshold.
- Flags team member comments via ``team_uids``.
- Produces per-team-member hot status summaries.
- Detects changes between consecutive status snapshots.

Design notes
------------
- The ranking algorithm is intentionally simple and configurable — no time
  decay or complex scoring.  ``flow_param`` is stored for future use (Weibo's
  ``flow`` parameter) but does not affect ranking logic here.
- ``min_likes`` filters out low-quality comments before ranking.
- :meth:`analyze` mutates the input CommentDTO objects (rank, is_hot,
  is_team_member) since Pydantic models are mutable by default.
- :meth:`get_team_hot_status` returns plain dicts (not DTOs) for easy
  serialisation and comparison by :meth:`detect_changes`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from app.schemas.comment import CommentDTO


@dataclass
class HotConfig:
    """Configuration for :class:`HotCommentAnalyzer`.

    Attributes
    ----------
    top_n
        Number of top-ranked comments considered "hot".  Default 50.
    min_likes
        Minimum like count for a comment to be included in ranking.
        Comments below this threshold are excluded.  Default 0 (no filter).
    ranking_field
        CommentDTO field used for sorting (descending).  Default
        ``"like_count"``.
    flow_param
        Weibo ``flow`` parameter (0 = hot sort).  Stored for future use,
        does not affect ranking logic.  Default 0.
    """

    top_n: int = 50
    min_likes: int = 0
    ranking_field: str = "like_count"
    flow_param: int = 0


class HotCommentAnalyzer:
    """Analyze comment lists for hot ranking and team member status.

    Parameters
    ----------
    config
        :class:`HotConfig` instance.  When ``None``, default config is used.
    """

    def __init__(self, config: Optional[HotConfig] = None) -> None:
        self.config = config or HotConfig()

    # ------------------------------------------------------------------
    # Core analysis
    # ------------------------------------------------------------------

    def analyze(
        self,
        comments: list[CommentDTO],
        team_uids: list[str],
    ) -> list[CommentDTO]:
        """Rank, flag, and annotate a list of comments.

        Steps:
        1. Filter by ``min_likes``.
        2. Sort by ``ranking_field`` descending.
        3. Assign ``rank`` starting at 1.
        4. Set ``is_hot = rank <= config.top_n``.
        5. Set ``is_team_member = user_uid in team_uids``.

        Parameters
        ----------
        comments
            List of :class:`~app.schemas.comment.CommentDTO` objects.
        team_uids
            List of team member UIDs for flagging.

        Returns
        -------
        list[CommentDTO]
            The sorted, annotated comment list (same objects, mutated).
        """
        if not comments:
            return []

        team_set = set(team_uids)

        # Filter by min_likes.
        filtered = [
            c for c in comments
            if getattr(c, self.config.ranking_field, 0) >= self.config.min_likes
        ]

        # Sort by ranking field descending.
        ranked = sorted(
            filtered,
            key=lambda c: getattr(c, self.config.ranking_field, 0),
            reverse=True,
        )

        # Assign rank, is_hot, is_team_member.
        for idx, comment in enumerate(ranked):
            rank = idx + 1
            comment.rank = rank
            comment.is_hot = rank <= self.config.top_n
            comment.is_team_member = comment.user_uid in team_set

        return ranked

    # ------------------------------------------------------------------
    # Team hot status
    # ------------------------------------------------------------------

    def get_team_hot_status(
        self,
        comments: list[CommentDTO],
        team_uids: list[str],
    ) -> list[dict[str, Any]]:
        """Build per-team-member hot status summary.

        For each team UID:
        - Finds their best-ranked comment (lowest rank number).
        - Returns a dict with: uid, nickname, comment_id, rank, like_count,
          is_hot.
        - If no comment exists for a member, returns a dict with None values
          and ``is_hot=False``.

        Parameters
        ----------
        comments
            Pre-analyzed comment list (should be output of :meth:`analyze`).
        team_uids
            List of team member UIDs.

        Returns
        -------
        list[dict]
            One dict per team UID.
        """
        # Group comments by user_uid, tracking the best (lowest) rank.
        best_by_uid: dict[str, CommentDTO] = {}
        for comment in comments:
            if comment.user_uid not in team_uids:
                continue
            existing = best_by_uid.get(comment.user_uid)
            if existing is None or comment.rank < existing.rank:
                best_by_uid[comment.user_uid] = comment

        statuses: list[dict[str, Any]] = []
        for uid in team_uids:
            comment = best_by_uid.get(uid)
            if comment is not None:
                statuses.append({
                    "uid": uid,
                    "nickname": comment.user_name,
                    "comment_id": comment.weibo_comment_id,
                    "rank": comment.rank,
                    "like_count": comment.like_count,
                    "is_hot": comment.is_hot,
                })
            else:
                statuses.append({
                    "uid": uid,
                    "nickname": None,
                    "comment_id": None,
                    "rank": None,
                    "like_count": None,
                    "is_hot": False,
                })

        return statuses

    # ------------------------------------------------------------------
    # Change detection
    # ------------------------------------------------------------------

    def detect_changes(
        self,
        prev_status: list[dict],
        curr_status: list[dict],
    ) -> dict[str, list]:
        """Compare previous and current team hot status lists.

        Returns a dict with three keys:

        - ``entered_hot``: UIDs of members who were not hot before but are
          hot now (includes members who are new in ``curr_status`` and hot).
        - ``dropped_out``: UIDs of members who were hot before but not hot
          now (includes members who disappeared from ``curr_status``).
        - ``rank_changed``: List of dicts ``{uid, prev_rank, curr_rank}``
          for members whose rank changed while remaining hot in both
          snapshots.

        Parameters
        ----------
        prev_status
            Previous team hot status (output of :meth:`get_team_hot_status`).
        curr_status
            Current team hot status.

        Returns
        -------
        dict
            ``{"entered_hot": [...], "dropped_out": [...], "rank_changed": [...]}``.
        """
        prev_by_uid: dict[str, dict] = {s["uid"]: s for s in prev_status}
        curr_by_uid: dict[str, dict] = {s["uid"]: s for s in curr_status}

        entered_hot: list[str] = []
        dropped_out: list[str] = []
        rank_changed: list[dict] = []

        # Members in both prev and curr.
        for uid, curr in curr_by_uid.items():
            prev = prev_by_uid.get(uid)

            if prev is None:
                # New member in curr.
                if curr.get("is_hot", False):
                    entered_hot.append(uid)
                continue

            prev_hot = prev.get("is_hot", False)
            curr_hot = curr.get("is_hot", False)

            if not prev_hot and curr_hot:
                entered_hot.append(uid)
            elif prev_hot and not curr_hot:
                dropped_out.append(uid)
            elif prev_hot and curr_hot:
                # Both hot — check rank change.
                prev_rank = prev.get("rank")
                curr_rank = curr.get("rank")
                if prev_rank != curr_rank:
                    rank_changed.append({
                        "uid": uid,
                        "prev_rank": prev_rank,
                        "curr_rank": curr_rank,
                    })

        # Members in prev but not in curr.
        for uid, prev in prev_by_uid.items():
            if uid not in curr_by_uid:
                if prev.get("is_hot", False):
                    dropped_out.append(uid)

        return {
            "entered_hot": entered_hot,
            "dropped_out": dropped_out,
            "rank_changed": rank_changed,
        }
