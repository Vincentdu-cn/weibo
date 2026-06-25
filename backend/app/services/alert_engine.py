"""Alert engine — processes hot-comment status changes into actionable alerts.

Provides :class:`AlertEngine` which:
- Consumes the change dict produced by
  :meth:`~app.services.hot_analyzer.HotCommentAnalyzer.detect_changes`.
- Creates :class:`~app.models.alert.Alert` records for dropped-out, entered-hot,
  and significant rank-drop events.
- Manages alert lifecycle: ``pending`` → ``confirmed`` / ``dismissed``.
- Attaches human-confirmed action parameters (comment text, target accounts).
- Broadcasts WebSocket events (``alert_new``, ``alert_resolved``) when a
  :class:`~app.services.ws_manager.WebSocketConnectionManager` is supplied.

Design notes
------------
- **DB-optional**: when ``db_session`` is ``None``, Alert objects are still
  created in memory but not persisted, and all DB-returning methods return
  empty results.
- **WS-optional**: when ``ws_manager`` is ``None``, all broadcast calls are
  silently skipped.
- **Async**: ``process_changes``, ``resolve_alert``, and ``attach_action`` are
  coroutine methods because they may need to ``await`` WSManager.broadcast.
- **Rank-drop threshold**: only drops greater than 10 positions trigger an
  alert (configurable via ``RANK_DROP_THRESHOLD``).
- **Action data storage**: the Alert model has no dedicated columns for
  ``comment_content`` or ``selected_account_ids``.  These are stored as a
  JSON string appended to the ``message`` field so they survive DB
  round-trips and can be parsed by downstream tasks.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from app.models.alert import Alert

# Minimum rank drop (curr_rank - prev_rank) to trigger a rank_drop alert.
RANK_DROP_THRESHOLD: int = 10


class AlertEngine:
    """Process hot-comment changes into alerts and manage alert lifecycle.

    Parameters
    ----------
    db_session
        Optional SQLAlchemy session.  When ``None``, alerts are created
        in memory only (not persisted, no queries).
    ws_manager
        Optional :class:`WebSocketConnectionManager`.  When ``None``,
        all broadcast calls are skipped.
    """

    def __init__(self, db_session: Any = None, ws_manager: Any = None) -> None:
        self.db_session = db_session
        self.ws_manager = ws_manager

    # ------------------------------------------------------------------
    # Core: process changes
    # ------------------------------------------------------------------

    async def process_changes(self, changes: dict) -> list[Alert]:
        """Create alerts from a ``detect_changes()`` result dict.

        Parameters
        ----------
        changes
            Dict with keys ``entered_hot``, ``dropped_out``,
            ``rank_changed`` (output of
            :meth:`HotCommentAnalyzer.detect_changes`).

        Returns
        -------
        list[Alert]
            All created Alert objects (persisted to DB if session exists).
        """
        alerts: list[Alert] = []

        dropped_out = changes.get("dropped_out", [])
        entered_hot = changes.get("entered_hot", [])
        rank_changed = changes.get("rank_changed", [])

        # Dropped out of hot comments.
        for uid in dropped_out:
            alert = Alert(
                alert_type="dropped_out",
                status="pending",
                account_uid=uid,
                message=f"组员{uid}掉出热评",
            )
            alerts.append(alert)

        # Entered hot comments.
        for uid in entered_hot:
            alert = Alert(
                alert_type="entered_hot",
                status="pending",
                account_uid=uid,
                message=f"组员{uid}进入热评",
            )
            alerts.append(alert)

        # Significant rank drop (> threshold positions).
        for rc in rank_changed:
            uid = rc["uid"]
            prev_rank = rc["prev_rank"]
            curr_rank = rc["curr_rank"]
            drop = curr_rank - prev_rank
            if drop > RANK_DROP_THRESHOLD:
                alert = Alert(
                    alert_type="rank_drop",
                    status="pending",
                    account_uid=uid,
                    message=f"组员{uid}排名下降{drop}位",
                )
                alerts.append(alert)

        # Persist + broadcast.
        if self.db_session is not None:
            for alert in alerts:
                self.db_session.add(alert)
            self.db_session.commit()
            # Refresh to get auto-generated IDs.
            for alert in alerts:
                self.db_session.refresh(alert)

        if self.ws_manager is not None:
            for alert in alerts:
                await self.ws_manager.broadcast(
                    "alert_new",
                    {
                        "alert_id": alert.id,
                        "alert_type": alert.alert_type,
                        "account_uid": alert.account_uid,
                        "message": alert.message,
                        "status": alert.status,
                    },
                )

        return alerts

    # ------------------------------------------------------------------
    # Query: pending alerts
    # ------------------------------------------------------------------

    def get_pending_alerts(self) -> list[Alert]:
        """Return all alerts with ``status='pending'``.

        Returns
        -------
        list[Alert]
            Pending alerts from DB, or empty list when no DB session.
        """
        if self.db_session is None:
            return []

        return (
            self.db_session.query(Alert)
            .filter(Alert.status == "pending")
            .all()
        )

    # ------------------------------------------------------------------
    # Lifecycle: resolve alert
    # ------------------------------------------------------------------

    async def resolve_alert(
        self,
        alert_id: int,
        action: str = "confirmed",
    ) -> bool:
        """Update an alert's status to ``confirmed`` or ``dismissed``.

        Parameters
        ----------
        alert_id
            Primary key of the Alert to resolve.
        action
            New status — ``"confirmed"`` or ``"dismissed"``.

        Returns
        -------
        bool
            ``True`` if the alert was found and updated, ``False`` otherwise.
        """
        if self.db_session is None:
            return False

        alert = (
            self.db_session.query(Alert)
            .filter(Alert.id == alert_id)
            .first()
        )
        if alert is None:
            return False

        alert.status = action
        self.db_session.commit()

        if self.ws_manager is not None:
            await self.ws_manager.broadcast(
                "alert_resolved",
                {
                    "alert_id": alert.id,
                    "status": alert.status,
                },
            )

        return True

    # ------------------------------------------------------------------
    # Lifecycle: attach action
    # ------------------------------------------------------------------

    async def attach_action(
        self,
        alert_id: int,
        comment_content: str,
        selected_account_ids: list[str],
    ) -> bool:
        """Confirm an alert and attach human-provided action parameters.

        Sets ``status='confirmed'`` and stores ``comment_content`` and
        ``selected_account_ids`` as a JSON payload appended to the alert's
        ``message`` field (the model has no dedicated columns for these).

        Parameters
        ----------
        alert_id
            Primary key of the Alert.
        comment_content
            The comment text the operator wants to post.
        selected_account_ids
            UIDs of accounts that should execute the action.

        Returns
        -------
        bool
            ``True`` if found and updated, ``False`` otherwise.
        """
        if self.db_session is None:
            return False

        alert = (
            self.db_session.query(Alert)
            .filter(Alert.id == alert_id)
            .first()
        )
        if alert is None:
            return False

        alert.status = "confirmed"

        # Store action data as JSON in the message field.
        action_data = {
            "original_message": alert.message,
            "comment_content": comment_content,
            "selected_account_ids": selected_account_ids,
        }
        alert.message = json.dumps(action_data, ensure_ascii=False)

        self.db_session.commit()

        if self.ws_manager is not None:
            await self.ws_manager.broadcast(
                "alert_resolved",
                {
                    "alert_id": alert.id,
                    "status": alert.status,
                    "comment_content": comment_content,
                    "selected_account_ids": selected_account_ids,
                },
            )

        return True
