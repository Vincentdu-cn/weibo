"""FastAPI routes for Weibo QR-code login.

Provides two endpoints:
  GET /api/qr/generate             — request a new QR code image + session ID
  GET /api/qr/status/{session_id}  — poll the login status for a session
"""

from __future__ import annotations

from fastapi import APIRouter

from app.services.qr_login import WeiboQrLogin

router = APIRouter(prefix="/api/qr", tags=["qr-login"])

# Module-level singleton — the AsyncClient is lazy, so creating it at import
# time is safe; it only opens connections when a request is actually made.
qr_login = WeiboQrLogin()


@router.get("/generate")
async def generate_qr() -> dict:
    """Generate a new QR code for Weibo SSO login.

    Returns:
        ``{"qr_image_url": str, "session_id": str}``
    """
    return await qr_login.get_qr_image()


@router.get("/status/{session_id}")
async def check_status(session_id: str) -> dict:
    """Check the login status for a QR session.

    Returns:
        ``{"status": "qr_awaiting" | "qr_scanned" | "qr_confirmed", ...}``
        On success also includes ``cookie``, ``weibo_uid`` and ``nickname``.
    """
    return await qr_login.check_login_status(session_id)
