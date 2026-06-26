"""Action executor for Weibo comment operations.

Implements comment liking (updateLike), batch liking with anti-detection
delays, and unliking (destroyLike) via the Weibo AJAX API.

Design notes
------------
- Uses ``updateLike`` with ``object_type="comment"`` — NOT ``setLike``.
- Batch liking is strictly sequential with ``wait_action()`` delays between
  each like.  No parallelisation — sequential execution is safer for
  anti-detection.
- Every action is optionally logged to the ``ActionLog`` table when a
  database session is provided.
- The class is designed to be **extensible**: Task 13 will add comment
  posting methods (``post_comment``, ``reply_comment``) to this same file.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from app.services.anti_detection import AntiDetectionEngine
from app.services.weibo_client import WeiboHttpClient

logger = logging.getLogger(__name__)

# -- API endpoints ----------------------------------------------------------

_LIKE_PATH = "/ajax/statuses/updateLike"
_UNLIKE_PATH = "/ajax/statuses/destroyLike"
_COMMENT_CREATE_PATH = "/ajax/comments/create"
_COMMENT_REPLY_PATH = "/ajax/comments/reply"

# -- Result type aliases ----------------------------------------------------

LikeResult = dict[str, Any]  # {"success": bool, "error_msg": str | None}
BatchLikeResult = dict[str, Any]  # {"uid": str, "success": bool, "error_msg": str | None}
CommentResult = dict[str, Any]  # {"success": bool, "comment_id": str | None, "error_msg": str | None}

# -- Constants --------------------------------------------------------------

_COMMENT_LIMIT = 500


class ActionExecutor:
    """Executes Weibo comment actions: like, batch like, unlike.

    Parameters
    ----------
    client
        :class:`WeiboHttpClient` instance for making HTTP requests.
    anti_detection
        :class:`AntiDetectionEngine` for inter-action delays.
        If ``None``, a default instance is created.
    db_session
        Optional SQLAlchemy session for logging actions to ``ActionLog``.
        If ``None``, logging is skipped silently.
    """

    def __init__(
        self,
        client: WeiboHttpClient,
        anti_detection: Optional[AntiDetectionEngine] = None,
        db_session: Any = None,
    ) -> None:
        self.client = client
        self.anti_detection: AntiDetectionEngine = (
            anti_detection or AntiDetectionEngine()
        )
        self.db_session = db_session

    # ------------------------------------------------------------------
    # Like
    # ------------------------------------------------------------------

    async def like_comment(
        self,
        comment_id: str | int,
        cookie: str,
        uid: str = "unknown",
    ) -> LikeResult:
        """Like a single Weibo comment via ``POST /ajax/statuses/updateLike``.

        Parameters
        ----------
        comment_id
            The Weibo comment ID to like.  Converted to ``str`` internally.
        cookie
            Raw cookie header string for the account performing the like.
        uid
            Account UID for logging purposes.  Defaults to ``"unknown"``.

        Returns
        -------
        dict
            ``{"success": bool, "error_msg": str | None}``
        """
        data = {
            "object_id": str(comment_id),
            "object_type": "comment",
        }
        return await self._do_action(
            path=_LIKE_PATH,
            data=data,
            cookie=cookie,
            uid=uid,
            comment_id=str(comment_id),
            action_type="like",
        )

    # ------------------------------------------------------------------
    # Batch Like
    # ------------------------------------------------------------------

    async def batch_like(
        self,
        comment_id: str | int,
        cookies: list[tuple[str, str]],
    ) -> list[BatchLikeResult]:
        """Sequentially like a comment with multiple account cookies.

        Each like is performed one-at-a-time with an
        :meth:`AntiDetectionEngine.wait_action` delay (5-15s) **between**
        consecutive likes.  No delay before the first or after the last.

        Parameters
        ----------
        comment_id
            The Weibo comment ID to like.
        cookies
            List of ``(uid, cookie_str)`` tuples — one per support account.

        Returns
        -------
        list[dict]
            ``[{"uid": str, "success": bool, "error_msg": str | None}]``
            — exactly one entry per cookie, in the same order.
        """
        results: list[BatchLikeResult] = []
        cid = str(comment_id)

        for i, (uid, cookie) in enumerate(cookies):
            # Delay between likes (not before first, not after last)
            if i > 0:
                await self.anti_detection.wait_action()

            result = await self.like_comment(cid, cookie, uid=uid)
            results.append(
                {
                    "uid": uid,
                    "success": result["success"],
                    "error_msg": result["error_msg"],
                }
            )

        return results

    # ------------------------------------------------------------------
    # Batch Like Comments (single operator cookie, multiple comments)
    # ------------------------------------------------------------------

    async def batch_like_comments(
        self,
        comment_ids: list[str],
        cookie: str,
        uid: str = "operator",
    ) -> list[LikeResult]:
        """Like multiple comments sequentially with a single account cookie.

        This is the *single operator* mode: one logged-in account likes ALL
        team-member comments.  Each like is performed one-at-a-time with an
        :meth:`AntiDetectionEngine.wait_action` delay (8-20s) **between**
        consecutive likes.  No delay before the first or after the last.

        Parameters
        ----------
        comment_ids
            List of Weibo comment IDs to like.  Each is converted to ``str``
            internally.
        cookie
            Raw cookie header string for the single operator account.
        uid
            Account UID for logging purposes.  Defaults to ``"operator"``.

        Returns
        -------
        list[dict]
            ``[{"success": bool, "error_msg": str | None}]``
            — exactly one entry per ``comment_id``, in the same order.
        """
        results: list[LikeResult] = []

        for i, cid in enumerate(comment_ids):
            # Delay between likes (not before first, not after last)
            if i > 0:
                await self.anti_detection.wait_action()

            result = await self.like_comment(cid, cookie, uid=uid)
            results.append(result)

        return results

    # ------------------------------------------------------------------
    # Unlike
    # ------------------------------------------------------------------

    async def unlike_comment(
        self,
        comment_id: str | int,
        cookie: str,
        uid: str = "unknown",
    ) -> LikeResult:
        """Unlike a Weibo comment via ``POST /ajax/statuses/destroyLike``.

        Parameters
        ----------
        comment_id
            The Weibo comment ID to unlike.  Converted to ``str`` internally.
        cookie
            Raw cookie header string for the account performing the unlike.
        uid
            Account UID for logging purposes.

        Returns
        -------
        dict
            ``{"success": bool, "error_msg": str | None}``
        """
        data = {
            "object_id": str(comment_id),
            "object_type": "comment",
        }
        return await self._do_action(
            path=_UNLIKE_PATH,
            data=data,
            cookie=cookie,
            uid=uid,
            comment_id=str(comment_id),
            action_type="unlike",
        )

    # ------------------------------------------------------------------
    # Post Comment
    # ------------------------------------------------------------------

    async def post_comment(
        self,
        weibo_mid: str | int,
        content: str,
        cookie: str,
        uid: str = "unknown",
    ) -> CommentResult:
        """Post a new comment on a Weibo post via ``POST /ajax/comments/create``.

        Returns ``{"success": bool, "comment_id": str | None, "error_msg": str | None}``.

        Enforces a 500-comment limit per CompetitionSession when a DB session
        is available.  After a successful post, ``total_comments`` is
        incremented by 1.
        """
        if self._comment_limit_reached():
            return {
                "success": False,
                "comment_id": None,
                "error_msg": f"Comment limit reached ({_COMMENT_LIMIT})",
            }

        data = {
            "id": str(weibo_mid),
            "comment": content,
            "pic_id": "",
            "is_repost": 0,
            "comment_ori": 0,
            "is_comment": 0,
        }
        result = await self._do_comment(
            path=_COMMENT_CREATE_PATH,
            data=data,
            cookie=cookie,
            uid=uid,
            action_type="comment",
            target_comment_id="",
        )

        if result["success"] and self.db_session is not None:
            self._increment_comment_count()

        return result

    # ------------------------------------------------------------------
    # Reply Comment
    # ------------------------------------------------------------------

    async def reply_comment(
        self,
        weibo_mid: str | int,
        comment_id: str | int,
        content: str,
        cookie: str,
        uid: str = "unknown",
    ) -> CommentResult:
        """Reply to an existing comment via ``POST /ajax/comments/reply``.

        Returns ``{"success": bool, "comment_id": str | None, "error_msg": str | None}``.

        Same 500-comment limit enforcement as :meth:`post_comment`.
        """
        if self._comment_limit_reached():
            return {
                "success": False,
                "comment_id": None,
                "error_msg": f"Comment limit reached ({_COMMENT_LIMIT})",
            }

        data = {
            "id": str(weibo_mid),
            "cid": str(comment_id),
            "comment": content,
            "pic_id": "",
            "is_repost": 0,
            "comment_ori": 0,
            "is_comment": 0,
        }
        result = await self._do_comment(
            path=_COMMENT_REPLY_PATH,
            data=data,
            cookie=cookie,
            uid=uid,
            action_type="reply",
            target_comment_id=str(comment_id),
        )

        if result["success"] and self.db_session is not None:
            self._increment_comment_count()

        return result

    # ------------------------------------------------------------------
    # Batch Comment
    # ------------------------------------------------------------------

    async def batch_comment(
        self,
        weibo_mid: str | int,
        content: str,
        cookies: list[tuple[str, str]],
    ) -> list[CommentResult]:
        """Sequentially post comments with multiple account cookies.

        Uses :meth:`AntiDetectionEngine.wait_comment` (10-20s) between each
        post — NOT ``wait_action()``.  Checks the 500-comment limit BEFORE
        each individual post.  Continues on individual failures.
        """
        results: list[CommentResult] = []

        for i, (uid, cookie) in enumerate(cookies):
            if i > 0:
                await self.anti_detection.wait_comment()

            result = await self.post_comment(weibo_mid, content, cookie, uid=uid)
            results.append(
                {
                    "uid": uid,
                    "success": result["success"],
                    "comment_id": result["comment_id"],
                    "error_msg": result["error_msg"],
                }
            )

        return results

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _do_comment(
        self,
        path: str,
        data: dict[str, str],
        cookie: str,
        uid: str,
        action_type: str,
        target_comment_id: str,
    ) -> CommentResult:
        """Execute a comment POST, parse the result, and log to DB.

        Handles the comment-specific response structure (``comment.id``
        extraction) that differs from the like/unlike flow in
        :meth:`_do_action`.
        """
        try:
            response = await self.client._post(path, data, cookie)
        except Exception as exc:
            logger.warning("Action %s failed with exception: %s", action_type, exc)
            self._log_action(
                uid=uid,
                action_type=action_type,
                comment_id=target_comment_id,
                status="failed",
                response=str(exc),
            )
            return {"success": False, "comment_id": None, "error_msg": str(exc)}

        ok = response.get("ok", 0)
        comment_id = None
        if isinstance(response.get("comment"), dict):
            comment_id = response["comment"].get("id")

        if ok > 0 or comment_id is not None:
            self._log_action(
                uid=uid,
                action_type=action_type,
                comment_id=target_comment_id,
                status="success",
                response=json.dumps(response, ensure_ascii=False),
            )
            return {"success": True, "comment_id": comment_id, "error_msg": None}

        error_msg = response.get("msg") or response.get("message") or "Unknown error"
        logger.info(
            "Action %s returned ok=0: %s",
            action_type,
            error_msg,
        )
        self._log_action(
            uid=uid,
            action_type=action_type,
            comment_id=target_comment_id,
            status="failed",
            response=json.dumps(response, ensure_ascii=False),
        )
        return {"success": False, "comment_id": None, "error_msg": error_msg}

    def _comment_limit_reached(self) -> bool:
        """Check if the CompetitionSession has reached the 500-comment limit."""
        if self.db_session is None:
            return False
        from app.models.competition_session import CompetitionSession

        session = self.db_session.query(CompetitionSession).first()
        if session is None:
            return False
        return session.total_comments >= _COMMENT_LIMIT

    def _increment_comment_count(self) -> None:
        """Increment ``total_comments`` on the current CompetitionSession."""
        from app.models.competition_session import CompetitionSession

        session = self.db_session.query(CompetitionSession).first()
        if session is not None:
            session.total_comments += 1
            self.db_session.commit()

    async def _do_action(
        self,
        path: str,
        data: dict[str, str],
        cookie: str,
        uid: str,
        comment_id: str,
        action_type: str,
    ) -> LikeResult:
        """Execute a POST action, parse the result, and log to DB.

        Centralises the shared logic for like / unlike:
        1. Call ``WeiboHttpClient._post``
        2. Check ``ok`` field in the response
        3. Log to ``ActionLog`` if a DB session is available
        4. Return a standardised result dict

        On exception, returns ``{"success": False, "error_msg": str(exc)}``.
        """
        try:
            response = await self.client._post(path, data, cookie)
        except Exception as exc:
            logger.warning("Action %s failed with exception: %s", action_type, exc)
            self._log_action(
                uid=uid,
                action_type=action_type,
                comment_id=comment_id,
                status="failed",
                response=str(exc),
            )
            return {"success": False, "error_msg": str(exc)}

        ok = response.get("ok", 0)
        if ok > 0:
            self._log_action(
                uid=uid,
                action_type=action_type,
                comment_id=comment_id,
                status="success",
                response=json.dumps(response, ensure_ascii=False),
            )
            return {"success": True, "error_msg": None}

        # ok == 0 — failure (already liked, comment deleted, rate limited, etc.)
        error_msg = response.get("msg") or response.get("message") or "Unknown error"
        logger.info(
            "Action %s returned ok=0 for comment %s: %s",
            action_type,
            comment_id,
            error_msg,
        )
        self._log_action(
            uid=uid,
            action_type=action_type,
            comment_id=comment_id,
            status="failed",
            response=json.dumps(response, ensure_ascii=False),
        )
        return {"success": False, "error_msg": error_msg}

    def _log_action(
        self,
        uid: str,
        action_type: str,
        comment_id: str,
        status: str,
        response: str,
    ) -> None:
        """Write an ``ActionLog`` record if a DB session is available.

        Silently skips logging when ``self.db_session`` is ``None``.
        """
        if self.db_session is None:
            return

        from app.models.action_log import ActionLog

        log_entry = ActionLog(
            account_uid=uid,
            action_type=action_type,
            target_comment_id=comment_id,
            status=status,
            response=response,
        )
        self.db_session.add(log_entry)
        self.db_session.commit()
