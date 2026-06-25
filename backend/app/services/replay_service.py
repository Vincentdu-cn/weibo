"""ReplayService — replay and review past competition sessions.

Queries DB for session timeline, alerts, actions, and summary.
All methods are async and gracefully handle None db_session.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import (
    ActionLog,
    Alert,
    Comment,
    CommentSnapshot,
    CompetitionSession,
)


class ReplayService:
    """Service for replaying and reviewing past competition sessions."""

    def __init__(self, db_session: Session | None = None):
        self.db_session = db_session

    # ── get_sessions ────────────────────────────────────────────────────────

    async def get_sessions(self) -> list[dict[str, Any]]:
        """Return a list of all competition sessions for replay selection."""
        if self.db_session is None:
            return []

        sessions = (
            self.db_session.query(CompetitionSession)
            .order_by(CompetitionSession.started_at.desc())
            .all()
        )

        return [
            {
                "id": s.id,
                "target_weibo_url": s.target_weibo_url,
                "target_weibo_mid": s.target_weibo_mid,
                "started_at": s.started_at.isoformat() if s.started_at else None,
                "ended_at": s.ended_at.isoformat() if s.ended_at else None,
                "total_comments": s.total_comments,
                "status": s.status,
            }
            for s in sessions
        ]

    # ── get_session_timeline ────────────────────────────────────────────────

    async def get_session_timeline(self, session_id: int) -> dict[str, Any]:
        """Return timeline of comment snapshots grouped by snapshot_at timestamp."""
        if self.db_session is None:
            return {"timeline": []}

        # Verify session exists
        session = self.db_session.query(CompetitionSession).filter_by(id=session_id).first()
        if session is None:
            return {"timeline": []}

        # Get comment IDs for this session's post (via weibo_post_id = target_weibo_mid)
        comments = self.db_session.query(Comment).filter_by(
            weibo_post_id=session.target_weibo_mid
        ).all()

        if not comments:
            return {"timeline": []}

        comment_ids = [c.id for c in comments]
        comment_map = {c.id: c for c in comments}

        # Get all snapshots for these comments, ordered by snapshot_at
        snapshots = (
            self.db_session.query(CommentSnapshot)
            .filter(CommentSnapshot.comment_id.in_(comment_ids))
            .order_by(CommentSnapshot.snapshot_at.asc())
            .all()
        )

        # Group snapshots by snapshot_at timestamp
        grouped: dict[datetime, list[CommentSnapshot]] = defaultdict(list)
        for snap in snapshots:
            grouped[snap.snapshot_at].append(snap)

        timeline = []
        for timestamp, snaps in sorted(grouped.items()):
            # Sort snaps by rank within each timestamp
            snaps_sorted = sorted(snaps, key=lambda s: (s.rank if s.rank is not None else 9999))
            comments_data = [
                {
                    "comment_id": snap.comment_id,
                    "rank": snap.rank,
                    "user_uid": comment_map.get(snap.comment_id, None).user_uid
                    if comment_map.get(snap.comment_id)
                    else None,
                    "user_name": comment_map.get(snap.comment_id, None).user_name
                    if comment_map.get(snap.comment_id)
                    else None,
                    "like_count": snap.like_count,
                    "is_hot": snap.is_hot,
                    "is_team_member": snap.is_team_member,
                }
                for snap in snaps_sorted
            ]
            timeline.append({
                "timestamp": timestamp.isoformat() if timestamp else None,
                "comments": comments_data,
            })

        return {"timeline": timeline}

    # ── get_session_alerts ──────────────────────────────────────────────────

    async def get_session_alerts(self, session_id: int) -> dict[str, Any]:
        """Return all alerts for a given session."""
        if self.db_session is None:
            return {"alerts": []}

        alerts = (
            self.db_session.query(Alert)
            .filter(Alert.session_id == session_id)
            .order_by(Alert.created_at.asc())
            .all()
        )

        return {
            "alerts": [
                {
                    "id": a.id,
                    "alert_type": a.alert_type,
                    "message": a.message,
                    "status": a.status,
                    "account_uid": a.account_uid,
                    "comment_id": a.comment_id,
                    "created_at": a.created_at.isoformat() if a.created_at else None,
                }
                for a in alerts
            ]
        }

    # ── get_session_actions ─────────────────────────────────────────────────

    async def get_session_actions(self, session_id: int) -> dict[str, Any]:
        """Return all action logs within the session's time range.

        ActionLog doesn't have a session_id column, so we filter by the
        session's started_at..ended_at time window.
        """
        if self.db_session is None:
            return {"actions": []}

        session = self.db_session.query(CompetitionSession).filter_by(id=session_id).first()
        if session is None:
            return {"actions": []}

        # Build time range filter
        start = session.started_at
        end = session.ended_at or datetime.utcnow()

        query = self.db_session.query(ActionLog).filter(
            ActionLog.created_at >= start,
            ActionLog.created_at <= end,
        )
        actions = query.order_by(ActionLog.created_at.asc()).all()

        return {
            "actions": [
                {
                    "id": a.id,
                    "account_uid": a.account_uid,
                    "action_type": a.action_type,
                    "target_comment_id": a.target_comment_id,
                    "content": a.content,
                    "status": a.status,
                    "created_at": a.created_at.isoformat() if a.created_at else None,
                }
                for a in actions
            ]
        }

    # ── get_session_summary ─────────────────────────────────────────────────

    async def get_session_summary(self, session_id: int) -> dict[str, Any]:
        """Return aggregated summary metrics for a session."""
        empty_result: dict[str, Any] = {
            "total_comments": 0,
            "peak_hot_count": 0,
            "hot_ratio": 0.0,
            "action_success_rate": 0.0,
            "member_performance": [],
        }

        if self.db_session is None:
            return empty_result

        session = self.db_session.query(CompetitionSession).filter_by(id=session_id).first()
        if session is None:
            return empty_result

        # total_comments from session record
        total_comments = session.total_comments

        # Get comments for this session
        comments = self.db_session.query(Comment).filter_by(
            weibo_post_id=session.target_weibo_mid
        ).all()
        comment_ids = [c.id for c in comments]

        # peak_hot_count: max number of hot comments at any snapshot timestamp
        peak_hot_count = 0
        if comment_ids:
            snapshots = (
                self.db_session.query(CommentSnapshot)
                .filter(CommentSnapshot.comment_id.in_(comment_ids))
                .all()
            )

            # Group by snapshot_at and count hot
            hot_by_time: dict[datetime, int] = defaultdict(int)
            total_by_time: dict[datetime, int] = defaultdict(int)
            for snap in snapshots:
                total_by_time[snap.snapshot_at] += 1
                if snap.is_hot:
                    hot_by_time[snap.snapshot_at] += 1

            if hot_by_time:
                peak_hot_count = max(hot_by_time.values())

        # hot_ratio: ratio of team member comments that were ever hot
        hot_ratio = 0.0
        if comment_ids:
            team_member_comments = (
                self.db_session.query(CommentSnapshot)
                .filter(
                    CommentSnapshot.comment_id.in_(comment_ids),
                    CommentSnapshot.is_team_member == True,  # noqa: E712
                )
                .all()
            )
            team_member_hot = [s for s in team_member_comments if s.is_hot]
            if team_member_comments:
                hot_ratio = len(team_member_hot) / len(team_member_comments)

        # action_success_rate: success / total actions in session time range
        action_success_rate = 0.0
        start = session.started_at
        end = session.ended_at or datetime.utcnow()
        actions = (
            self.db_session.query(ActionLog)
            .filter(
                ActionLog.created_at >= start,
                ActionLog.created_at <= end,
            )
            .all()
        )
        if actions:
            success_count = sum(1 for a in actions if a.status == "success")
            action_success_rate = success_count / len(actions)

        # member_performance: aggregate per team member
        member_performance = []
        if comment_ids:
            # Get team member snapshots
            team_snapshots = (
                self.db_session.query(CommentSnapshot)
                .filter(
                    CommentSnapshot.comment_id.in_(comment_ids),
                    CommentSnapshot.is_team_member == True,  # noqa: E712
                )
                .all()
            )

            # Group by comment_id (which maps to a user)
            member_data: dict[int, dict[str, Any]] = defaultdict(lambda: {
                "like_count": 0,
                "comment_count": 0,
                "best_rank": 9999,
            })

            for snap in team_snapshots:
                comment = next((c for c in comments if c.id == snap.comment_id), None)
                if comment is None:
                    continue

                uid = comment.user_uid
                if uid not in member_data:
                    member_data[uid] = {
                        "uid": uid,
                        "name": comment.user_name,
                        "like_count": 0,
                        "comment_count": 0,
                        "best_rank": 9999,
                    }

                # Use latest snapshot's like_count
                if snap.like_count > member_data[uid]["like_count"]:
                    member_data[uid]["like_count"] = snap.like_count

                # Count unique comments per member
                member_data[uid]["comment_count"] = len(
                    set(s.comment_id for s in team_snapshots
                        if next((c for c in comments if c.id == s.comment_id), None)
                        and next(c for c in comments if c.id == s.comment_id).user_uid == uid)
                )

                # Best (lowest) rank
                if snap.rank is not None and snap.rank < member_data[uid]["best_rank"]:
                    member_data[uid]["best_rank"] = snap.rank

            # Convert to list and clean up
            for uid, data in member_data.items():
                if data["best_rank"] == 9999:
                    data["best_rank"] = None
                member_performance.append(data)

        return {
            "total_comments": total_comments,
            "peak_hot_count": peak_hot_count,
            "hot_ratio": round(hot_ratio, 4),
            "action_success_rate": round(action_success_rate, 4),
            "member_performance": member_performance,
        }
