"""FastAPI routes for batch Weibo comment actions.

Provides endpoints:
  POST /api/actions/batch-like — like multiple comments with the operator account
"""

from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.api.ws import ws_manager
from app.core.database import SessionLocal
from app.models.account import Account
from app.services.action_executor import ActionExecutor
from app.services.weibo_client import WeiboHttpClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/actions", tags=["actions"])


class BatchLikeRequest(BaseModel):
    comment_ids: list[str]


def _parse_cookie_string(cookie_json: str | None) -> str:
    """Convert the stored cookie_json field into a cookie header string.

    The cookie_json field may store either a JSON dict
    (``{"SUB": "abc", "XSRF-TOKEN": "xyz"}``) or a raw cookie header
    string (``SUB=abc; XSRF-TOKEN=xyz``).  Both formats are handled.
    """
    if not cookie_json:
        return ""
    try:
        parsed = json.loads(cookie_json)
        if isinstance(parsed, dict):
            return "; ".join(f"{k}={v}" for k, v in parsed.items())
    except (json.JSONDecodeError, ValueError, TypeError):
        pass
    return cookie_json


async def _run_batch_like_background(
    comment_ids: list[str],
    cookie: str,
    uid: str,
) -> None:
    """Background task: warmup cookie, like each comment, broadcast progress.

    Uses the same sequential pattern as
    :meth:`ActionExecutor.batch_like_comments` — ``wait_action()`` between
    likes (not before first, not after last) — but broadcasts progress via
    WebSocket after each individual like.
    """
    total = len(comment_ids)
    success_count = 0
    fail_count = 0

    client = WeiboHttpClient()
    executor = ActionExecutor(client=client)

    try:
        warmed_cookie = await client.warmup_cookie(cookie)

        for i, cid in enumerate(comment_ids):
            if i > 0:
                await executor.anti_detection.wait_action()

            result = await executor.like_comment(cid, warmed_cookie, uid=uid)

            if result["success"]:
                success_count += 1
            else:
                fail_count += 1

            await ws_manager.broadcast(
                "batch_like_progress",
                {
                    "current": i + 1,
                    "total": total,
                    "current_comment_id": cid,
                    "success": result["success"],
                    "error": result["error_msg"],
                    "status": "running",
                },
            )

        await ws_manager.broadcast(
            "batch_like_progress",
            {
                "current": total,
                "total": total,
                "status": "done",
                "success_count": success_count,
                "fail_count": fail_count,
            },
        )
    except Exception:
        logger.exception("batch_like background task failed")
        await ws_manager.broadcast(
            "batch_like_progress",
            {
                "current": success_count + fail_count,
                "total": total,
                "status": "error",
                "success_count": success_count,
                "fail_count": fail_count,
            },
        )
    finally:
        await client.close()


@router.post("/batch-like", response_model=None)
async def batch_like(request: BatchLikeRequest) -> dict | JSONResponse:
    """Start a batch like operation using the operator account.

    Gets the first active account from the DB (the operator), parses its
    cookie, and launches a background task that warms up the cookie and
    likes each comment sequentially with anti-detection delays.

    Progress is broadcast via WebSocket as each comment is liked.

    Returns immediately with ``{"task_started": true, "total": N}``.
    Returns 400 if no active account with a cookie is found.
    """
    if not request.comment_ids:
        return {"task_started": False, "total": 0}

    db = SessionLocal()
    try:
        account = db.query(Account).filter(Account.status == "active").first()

        if account is None or not account.cookie_json:
            return JSONResponse(
                status_code=400,
                content={"error": "No operator account with cookie found"},
            )

        cookie = _parse_cookie_string(account.cookie_json)
        uid = account.weibo_uid or "operator"
    finally:
        db.close()

    asyncio.create_task(
        _run_batch_like_background(request.comment_ids, cookie, uid)
    )

    return {"task_started": True, "total": len(request.comment_ids)}
