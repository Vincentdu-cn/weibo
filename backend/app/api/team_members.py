"""FastAPI routes for TeamMember CRUD management.

Provides endpoints:
  GET    /api/team-members         — list all team members
  POST   /api/team-members         — add a single member
  POST   /api/team-members/batch   — batch add members (skip duplicates)
  DELETE /api/team-members/{id}    — delete a member
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db, init_db
from app.models.team_member import TeamMember

# Ensure database tables exist on module import
init_db()

router = APIRouter(prefix="/api", tags=["team-members"])


def _member_to_dto(member: TeamMember) -> dict:
    """Convert a TeamMember model instance to a DTO dict."""
    return {
        "id": member.id,
        "weibo_uid": member.weibo_uid,
        "nickname": member.nickname,
    }


# ── List ─────────────────────────────────────────────────────────────────


@router.get("/team-members")
async def list_team_members(db: Session = Depends(get_db)) -> list[dict]:
    """List all team members.

    Returns:
        A list of ``{id, weibo_uid, nickname}`` dicts ordered by creation time.
    """
    members = db.query(TeamMember).order_by(TeamMember.created_at.desc()).all()
    return [_member_to_dto(m) for m in members]


# ── Add single ───────────────────────────────────────────────────────────


@router.post("/team-members", status_code=201)
async def create_team_member(
    body: dict, db: Session = Depends(get_db)
) -> dict:
    """Add a single team member.

    Body:
        ``{"weibo_uid": str, "nickname": str}``

    Returns:
        ``{id, weibo_uid, nickname}``

    Raises:
        409 if the ``weibo_uid`` already exists.
    """
    weibo_uid = body.get("weibo_uid", "")
    nickname = body.get("nickname", "")

    if not weibo_uid or not nickname:
        raise HTTPException(status_code=422, detail="weibo_uid and nickname are required")

    existing = (
        db.query(TeamMember).filter(TeamMember.weibo_uid == weibo_uid).first()
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail="Team member with this weibo_uid already exists")

    member = TeamMember(weibo_uid=weibo_uid, nickname=nickname)
    db.add(member)
    db.commit()
    db.refresh(member)
    return _member_to_dto(member)


# ── Batch add ────────────────────────────────────────────────────────────


@router.post("/team-members/batch")
async def batch_create_team_members(
    body: list[dict], db: Session = Depends(get_db)
) -> dict:
    """Batch add team members, skipping duplicates.

    Body:
        A JSON array of ``{"weibo_uid": str, "nickname": str}`` objects.

    Returns:
        ``{"created": int, "skipped": int}``
    """
    created = 0
    skipped = 0

    # Pre-load existing UIDs for efficient duplicate detection.
    existing_uids: set[str] = {
        uid for (uid,) in db.query(TeamMember.weibo_uid).all()
    }

    for item in body:
        weibo_uid = item.get("weibo_uid", "")
        nickname = item.get("nickname", "")

        if not weibo_uid or not nickname:
            skipped += 1
            continue

        if weibo_uid in existing_uids:
            skipped += 1
            continue

        member = TeamMember(weibo_uid=weibo_uid, nickname=nickname)
        db.add(member)
        existing_uids.add(weibo_uid)
        created += 1

    db.commit()
    return {"created": created, "skipped": skipped}


# ── Delete ───────────────────────────────────────────────────────────────


@router.delete("/team-members/{member_id}", status_code=204)
async def delete_team_member(member_id: int, db: Session = Depends(get_db)) -> None:
    """Delete a team member by ID.

    Raises:
        404 if the member is not found.
    """
    member = db.query(TeamMember).filter(TeamMember.id == member_id).first()
    if member is None:
        raise HTTPException(status_code=404, detail="Team member not found")
    db.delete(member)
    db.commit()
