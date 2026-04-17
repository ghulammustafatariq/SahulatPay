"""Notification service — DB insert + FCM push. PROMPT 13."""
from __future__ import annotations

import asyncio
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.other import Notification
from models.user  import User


# ── FCM push helper ────────────────────────────────────────────────────────────
async def _push_fcm(fcm_token: str, title: str, body: str, data: dict) -> None:
    """Fire-and-forget FCM push via firebase-admin. Swallows all errors."""
    if not fcm_token:
        return
    try:
        from firebase_admin import messaging
        msg = messaging.Message(
            notification=messaging.Notification(title=title, body=body),
            data={str(k): str(v) for k, v in (data or {}).items()},
            token=fcm_token,
        )
        messaging.send(msg)
    except Exception:
        pass  # Never block on FCM failure


# ── Main public function ───────────────────────────────────────────────────────
async def send_notification(
    db: AsyncSession,
    user_id: UUID,
    title: str,
    body: str,
    type: str,
    data: Optional[dict[str, Any]] = None,
) -> Notification:
    """
    Insert a Notification row in Postgres, then fire FCM push non-blocking.

    type options: transaction | security | system | ai_insight | admin |
                  split | savings | investment | insurance | rewards | zakat
    """
    notif = Notification(
        user_id = user_id,
        title   = title,
        body    = body,
        type    = type,
        data    = data or {},
    )
    db.add(notif)
    await db.commit()
    await db.refresh(notif)

    # Get FCM token non-blockingly
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user and user.fcm_token:
        asyncio.create_task(_push_fcm(user.fcm_token, title, body, data or {}))

    return notif
