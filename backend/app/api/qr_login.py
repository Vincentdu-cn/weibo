"""FastAPI routes for Weibo QR-code login and account management.

Provides endpoints:
  GET    /api/qr/generate             — request a new QR code image + session ID
  GET    /api/qr/status/{session_id}  — poll the login status for a session
  GET    /api/accounts                — list all saved accounts
  DELETE /api/accounts/{id}           — delete (logout) an account
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db, init_db
from app.models.account import Account
from app.services.qr_login import WeiboQrLogin

# Ensure database tables exist on module import
init_db()

router = APIRouter(prefix="/api", tags=["qr-login"])

# Module-level singleton — the AsyncClient is lazy, so creating it at import
# time is safe; it only opens connections when a request is actually made.
qr_login = WeiboQrLogin()


def _account_to_dto(account: Account) -> dict:
    """Convert an Account model instance to an AccountDTO dict."""
    return {
        "id": account.id,
        "weibo_uid": account.weibo_uid,
        "nickname": account.nickname,
        "status": account.status,
        "avatar_url": account.avatar_url,
    }


# ── QR login endpoints ─────────────────────────────────────────────────────


@router.get("/qr/generate")
async def generate_qr() -> dict:
    """Generate a new QR code for Weibo SSO login.

    Returns:
        ``{"qr_url": str, "session_id": str}``
    """
    return await qr_login.get_qr_image()


@router.get("/qr/status/{session_id}")
async def check_status(session_id: str, db: Session = Depends(get_db)) -> dict:
    """Check the login status for a QR session.

    Returns:
        ``{"status": "waiting" | "scanned" | "success" | "expired", "account"?: AccountDTO}``
        On success, the account is saved to the database and included in the response.
    """
    result = await qr_login.check_login_status(session_id)

    if result.get("status") == "success":
        weibo_uid = result.get("weibo_uid", "")
        nickname = result.get("nickname", "")
        cookie = result.get("cookie", "")

        # Upsert the account: update if the weibo_uid already exists, else create
        account = (
            db.query(Account).filter(Account.weibo_uid == weibo_uid).first()
        )
        if account is None:
            account = Account(
                weibo_uid=weibo_uid,
                nickname=nickname,
                cookie_json=cookie,
                status="active",
            )
            db.add(account)
        else:
            account.nickname = nickname
            account.cookie_json = cookie
            account.status = "active"
        db.commit()
        db.refresh(account)

        result["account"] = _account_to_dto(account)

    # Strip internal fields (cookie, weibo_uid, nickname) from the response —
    # the frontend only needs status + account DTO.
    response: dict = {"status": result["status"]}
    if "account" in result:
        response["account"] = result["account"]
    return response


# ── Account management endpoints ───────────────────────────────────────────


@router.get("/accounts")
async def list_accounts(db: Session = Depends(get_db)) -> list[dict]:
    """List all saved accounts.

    Returns:
        A list of AccountDTO dicts.
    """
    accounts = db.query(Account).order_by(Account.created_at.desc()).all()
    return [_account_to_dto(a) for a in accounts]


@router.delete("/accounts/{account_id}")
async def delete_account(account_id: int, db: Session = Depends(get_db)) -> None:
    """Delete (log out) an account by ID."""
    account = db.query(Account).filter(Account.id == account_id).first()
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found")
    db.delete(account)
    db.commit()
