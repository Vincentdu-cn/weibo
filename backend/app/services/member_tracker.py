"""Team member tracker — maps analyzed comments to dashboard-ready member data.

Provides :class:`TeamMemberTracker` which:
- Loads team member UIDs from the TeamMember table.
- Matches pre-analyzed CommentDTO list against team UIDs.
- Produces per-member tracking data (all comments, aggregated stats).
- Generates a member grid for the dashboard UI (one card per member).

Design notes
------------
- Uses the output of :class:`~app.services.hot_analyzer.HotCommentAnalyzer.analyze`
  as input — comments already have ``rank``, ``is_hot``, ``is_team_member`` set.
- DB session is optional.  Without it, ``get_team_uids`` returns ``[]`` and
  ``_get_member_info`` returns unknown values.
- ``track_comments`` returns a dict keyed by UID for O(1) lookup.
- ``get_member_grid_data`` returns exactly one card per team member (no padding,
  no truncation).
"""

from __future__ import annotations

from typing import Any

from app.schemas.comment import CommentDTO


class TeamMemberTracker:
    """Track team member comment performance and produce dashboard grid data.

    Parameters
    ----------
    db_session
        Optional SQLAlchemy session for loading TeamMember table data.
        When ``None``, DB-dependent methods return empty/unknown results.
    """

    def __init__(self, db_session: Any = None) -> None:
        self.db_session = db_session

    # ------------------------------------------------------------------
    # Team UID loading
    # ------------------------------------------------------------------

    def get_team_uids(self) -> list[str]:
        """Load all ``weibo_uid`` values from the TeamMember table.

        Returns
        -------
        list[str]
            UIDs of all team members.  Empty list when no DB session or
            no members exist.
        """
        if self.db_session is None:
            return []

        from app.models.team_member import TeamMember

        members = self.db_session.query(TeamMember).all()
        return [m.weibo_uid for m in members]

    # ------------------------------------------------------------------
    # Comment tracking
    # ------------------------------------------------------------------

    def track_comments(
        self,
        comments: list[CommentDTO],
        team_uids: list[str],
    ) -> dict[str, dict]:
        """Match analyzed comments against team UIDs.

        For each team member, collects **all** their comments and computes
        aggregate statistics (total comments, total likes, best rank, hot
        status).

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
            Keyed by UID.  Each value has keys: ``nickname``,
            ``comments``, ``total_comments``, ``total_likes``,
            ``best_rank``, ``in_hot``.
            Members with no comments get empty ``comments`` list and
            zero/None aggregate values.
        """
        team_set = set(team_uids)

        # Group all comments by user_uid.
        comments_by_uid: dict[str, list[CommentDTO]] = {}
        for comment in comments:
            uid = comment.user_uid
            if uid not in team_set:
                continue
            comments_by_uid.setdefault(uid, []).append(comment)

        result: dict[str, dict] = {}
        for uid in team_uids:
            member_info = self._get_member_info(uid)
            member_comments = comments_by_uid.get(uid, [])

            # Build comment DTOs.
            comment_dicts: list[dict] = []
            total_likes = 0
            best_rank: int | None = None
            in_hot = False

            for c in member_comments:
                comment_dicts.append({
                    "comment_id": c.weibo_comment_id,
                    "content": c.content,
                    "like_count": c.like_count,
                    "rank": c.rank,
                    "is_hot": c.is_hot,
                    "created_at": c.created_at.isoformat() if c.created_at else None,
                })
                total_likes += c.like_count
                if best_rank is None or c.rank < best_rank:
                    best_rank = c.rank
                if c.is_hot:
                    in_hot = True

            result[uid] = {
                "nickname": member_info["nickname"],
                "comments": comment_dicts,
                "total_comments": len(member_comments),
                "total_likes": total_likes,
                "best_rank": best_rank,
                "in_hot": in_hot,
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
        """Return one status card per team member for the dashboard grid.

        Each card contains: ``uid``, ``nickname``, ``avatar_url``,
        ``total_comments``, ``total_likes``, ``best_rank``, ``in_hot``,
        ``comments``.

        Parameters
        ----------
        team_uids
            List of team member UIDs (order preserved).
        tracked
            Output of :meth:`track_comments` — per-UID tracking data.

        Returns
        -------
        list[dict]
            Exactly ``len(team_uids)`` card dicts — no padding, no
            truncation.
        """
        cards: list[dict] = []

        for uid in team_uids:
            tracked_info = tracked.get(uid, {})
            member_info = self._get_member_info(uid)

            # Prefer TeamMember nickname; fall back to tracked nickname.
            nickname = member_info["nickname"] or tracked_info.get("nickname")

            card = {
                "uid": uid,
                "nickname": nickname,
                "avatar_url": member_info["avatar_url"],
                "total_comments": tracked_info.get("total_comments", 0),
                "total_likes": tracked_info.get("total_likes", 0),
                "best_rank": tracked_info.get("best_rank"),
                "in_hot": tracked_info.get("in_hot", False),
                "comments": tracked_info.get("comments", []),
            }
            cards.append(card)

        return cards

    # ------------------------------------------------------------------
    # Member helper
    # ------------------------------------------------------------------

    def _get_member_info(self, uid: str) -> dict:
        """Query the TeamMember table for the given UID.

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

        from app.models.team_member import TeamMember

        member = (
            self.db_session.query(TeamMember)
            .filter(TeamMember.weibo_uid == uid)
            .first()
        )
        if member is None:
            return {"nickname": None, "avatar_url": None, "status": "unknown"}

        return {
            "nickname": member.nickname,
            "avatar_url": None,
            "status": "active",
        }
