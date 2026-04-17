"""Notifications router — list, unread count, mark read, delete. PROMPT 13."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.other import Notification
from models.user import User
from services.auth_service import get_current_user

router = APIRouter()


# ══════════════════════════════════════════════════════════════════════════════
# GET /notifications
# ══════════════════════════════════════════════════════════════════════════════
@router.get("")
async def list_notifications(
    page:     int = 1,
    per_page: int = 20,
    unread_only: bool = False,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Paginated notifications for current user, newest first."""
    q = select(Notification).where(Notification.user_id == current_user.id)
    if unread_only:
        q = q.where(Notification.is_read == False)
    q = q.order_by(Notification.created_at.desc())

    # Total count
    count_q = select(func.count()).select_from(
        select(Notification)
        .where(Notification.user_id == current_user.id)
        .where(Notification.is_read == False if unread_only else True == True)
        .subquery()
    )
    total_result = await db.execute(
        select(func.count(Notification.id)).where(
            Notification.user_id == current_user.id,
            *([] if not unread_only else [Notification.is_read == False]),
        )
    )
    total = total_result.scalar() or 0

    q = q.offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(q)
    items  = result.scalars().all()

    return {
        "notifications": [
            {
                "id":         n.id,
                "title":      n.title,
                "body":       n.body,
                "type":       n.type,
                "is_read":    n.is_read,
                "data":       n.data,
                "created_at": n.created_at.isoformat() if n.created_at else None,
            }
            for n in items
        ],
        "total":    total,
        "page":     page,
        "per_page": per_page,
        "has_next": (page * per_page) < total,
    }


# ══════════════════════════════════════════════════════════════════════════════
# GET /notifications/unread-count
# ══════════════════════════════════════════════════════════════════════════════
@router.get("/unread-count")
async def unread_count(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(func.count(Notification.id)).where(
            Notification.user_id == current_user.id,
            Notification.is_read == False,
        )
    )
    count = result.scalar() or 0
    return {"count": count}


# ══════════════════════════════════════════════════════════════════════════════
# POST /notifications/mark-all-read
# ══════════════════════════════════════════════════════════════════════════════
@router.post("/mark-all-read")
async def mark_all_read(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await db.execute(
        update(Notification)
        .where(
            Notification.user_id == current_user.id,
            Notification.is_read == False,
        )
        .values(is_read=True)
    )
    await db.commit()
    return {"message": "All notifications marked as read."}


# ══════════════════════════════════════════════════════════════════════════════
# PATCH /notifications/{id}/read
# ══════════════════════════════════════════════════════════════════════════════
@router.patch("/{notif_id}/read")
async def mark_one_read(
    notif_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    notif = (await db.execute(
        select(Notification).where(
            Notification.id      == notif_id,
            Notification.user_id == current_user.id,
        )
    )).scalar_one_or_none()

    if not notif:
        raise HTTPException(404, "Notification not found.")

    notif.is_read = True
    await db.commit()
    return {"message": "Notification marked as read.", "id": notif_id}


# ══════════════════════════════════════════════════════════════════════════════
# DELETE /notifications/{id}
# ══════════════════════════════════════════════════════════════════════════════
@router.delete("/{notif_id}")
async def delete_notification(
    notif_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    notif = (await db.execute(
        select(Notification).where(
            Notification.id      == notif_id,
            Notification.user_id == current_user.id,
        )
    )).scalar_one_or_none()

    if not notif:
        raise HTTPException(404, "Notification not found.")

    await db.delete(notif)
    await db.commit()
    return {"message": "Notification deleted.", "id": notif_id}
