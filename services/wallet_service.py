"""Wallet service — doTransfer engine, tier limits, pending-tx tokens."""
from __future__ import annotations

import asyncio
import secrets
import string
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Optional
from uuid import UUID

import bcrypt
from jose import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from models.user import User
from models.wallet import Wallet
from models.transaction import Transaction


# ── KYC tier daily limits (PKR) ───────────────────────────────────────────────
TIER_LIMITS: dict[int, Decimal] = {
    0: Decimal("0"),
    1: Decimal("25000"),
    2: Decimal("100000"),
    3: Decimal("500000"),
    4: Decimal("2000000"),
}


# ── Helpers ───────────────────────────────────────────────────────────────────
def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def generate_reference() -> str:
    """Unique 16-char alphanumeric reference — e.g. SPX4KR2QLMTA97BN"""
    chars = string.ascii_uppercase + string.digits
    return "SP" + "".join(secrets.choice(chars) for _ in range(14))


def verify_pin(pin: str, pin_hash: str) -> bool:
    return bcrypt.checkpw(pin.encode("utf-8"), pin_hash.encode("utf-8"))


def create_pending_tx_token(payload: dict) -> str:
    """5-minute signed JWT carrying transfer details — requires biometric confirm."""
    data = {**payload, "type": "pending_tx", "exp": _utcnow() + timedelta(minutes=5)}
    return jwt.encode(data, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_pending_tx_token(token: str) -> dict:
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])


# ── FCM helper ────────────────────────────────────────────────────────────────
async def _send_fcm(fcm_token: str, title: str, body: str) -> None:
    """Fire-and-forget FCM push. Swallows all errors — never blocks transfer."""
    if not fcm_token:
        return
    try:
        from firebase_admin import messaging
        messaging.send(messaging.Message(
            notification=messaging.Notification(title=title, body=body),
            token=fcm_token,
        ))
    except Exception as e:
        print(f"[FCM] {e}")


# ── Core transfer execution ───────────────────────────────────────────────────
async def _execute_transfer(
    db: AsyncSession,
    sender_wallet: Wallet,
    recipient_wallet: Wallet,
    sender: User,
    recipient: User,
    amount: Decimal,
    purpose: str,
    description: Optional[str],
    card_id: Optional[UUID],
) -> dict:
    """
    Atomic debit/credit. Caller must have already locked wallets with SELECT FOR UPDATE.
    Returns {reference_number, transaction_id, cashback_earned, new_balance}.
    """
    cashback = (amount * Decimal("0.01")).quantize(Decimal("0.01"))
    ref = generate_reference()

    sender_wallet.balance        -= amount
    sender_wallet.daily_spent     = (sender_wallet.daily_spent or Decimal("0")) + amount
    sender_wallet.cashback_pending = (sender_wallet.cashback_pending or Decimal("0")) + cashback
    sender_wallet.limit_reset_at  = _utcnow()
    recipient_wallet.balance      += amount

    if card_id:
        from models.card import VirtualCard
        card = (await db.execute(
            select(VirtualCard).where(VirtualCard.id == card_id).with_for_update()
        )).scalar_one_or_none()
        if card:
            card.monthly_spent = (card.monthly_spent or Decimal("0")) + amount

    sender_txn = Transaction(
        reference_number=ref,
        type="send",
        amount=amount,
        fee=Decimal("0"),
        cashback_earned=cashback,
        status="completed",
        sender_id=sender.id,
        recipient_id=recipient.id,
        purpose=purpose,
        description=description,
        completed_at=_utcnow(),
        tx_metadata={"card_id": str(card_id)} if card_id else {},
    )
    recipient_txn = Transaction(
        reference_number=ref + "R",
        type="receive",
        amount=amount,
        fee=Decimal("0"),
        cashback_earned=Decimal("0"),
        status="completed",
        sender_id=sender.id,
        recipient_id=recipient.id,
        purpose=purpose,
        description=description,
        completed_at=_utcnow(),
        tx_metadata={},
    )
    db.add(sender_txn)
    db.add(recipient_txn)
    await db.commit()
    await db.refresh(sender_txn)
    await db.refresh(sender_wallet)

    asyncio.create_task(_send_fcm(
        recipient.fcm_token or "",
        title=f"💸 PKR {amount:,.0f} Received",
        body=f"From {sender.full_name}. Ref: {ref}",
    ))

    # ── Cashback 1% on every outgoing transfer ────────────────────────────────
    try:
        from services.reward_service import add_cashback
        await add_cashback(db, sender.id, amount, sender_txn.id, purpose)
    except Exception as _cb_err:
        print(f"[wallet_service] cashback error (non-fatal): {_cb_err}")

    return {
        "status":           "completed",
        "reference_number": ref,
        "transaction_id":   sender_txn.id,
        "cashback_earned":  cashback,
        "new_balance":      sender_wallet.balance,
    }


# ── doTransfer — main entry point ─────────────────────────────────────────────
async def doTransfer(
    db: AsyncSession,
    sender_id: UUID,
    recipient_id: UUID,
    amount: Decimal,
    purpose: str,
    description: Optional[str],
    pin: Optional[str] = None,
    card_id: Optional[UUID] = None,
    biometric_confirmed: bool = False,
) -> dict:
    """
    Validates and (if amount < 1000 or biometric_confirmed) executes transfer.

    Returns:
      {"status": "completed", "reference_number": ..., "transaction_id": ...,
       "cashback_earned": ..., "new_balance": ...}
      OR
      {"status": "pending_biometric", "pending_tx_token": ...}  if amount >= 1000
    """
    from fastapi import HTTPException

    # ── Load sender ───────────────────────────────────────────────────────────
    sender = (await db.execute(
        select(User).where(User.id == sender_id)
    )).scalar_one_or_none()
    if not sender:
        raise HTTPException(404, "Sender not found")

    # ── PIN validation (skip only for biometric-confirmed flow) ───────────────
    if not biometric_confirmed:
        if not sender.pin_hash:
            raise HTTPException(400, "PIN not set. Please set your PIN first.")
        if not pin or not verify_pin(pin, sender.pin_hash):
            raise HTTPException(401, "Incorrect PIN")

    # ── Load recipient ────────────────────────────────────────────────────────
    recipient = (await db.execute(
        select(User).where(User.id == recipient_id)
    )).scalar_one_or_none()
    if not recipient:
        raise HTTPException(404, "Recipient not found")

    # ── SELECT FOR UPDATE — deadlock-safe (always lock lower UUID first) ──────
    ids_sorted = sorted([str(sender_id), str(recipient_id)])
    first_id   = UUID(ids_sorted[0])
    second_id  = UUID(ids_sorted[1])

    first_wallet = (await db.execute(
        select(Wallet).where(Wallet.user_id == first_id).with_for_update()
    )).scalar_one_or_none()
    second_wallet = (await db.execute(
        select(Wallet).where(Wallet.user_id == second_id).with_for_update()
    )).scalar_one_or_none()

    sender_wallet    = first_wallet  if first_id == sender_id    else second_wallet
    recipient_wallet = second_wallet if first_id == sender_id    else first_wallet

    if not sender_wallet:
        raise HTTPException(404, "Sender wallet not found")
    if not recipient_wallet:
        raise HTTPException(404, "Recipient wallet not found")

    # ── Wallet checks ─────────────────────────────────────────────────────────
    if sender_wallet.is_frozen:
        raise HTTPException(403, "Your wallet is frozen. Contact support.")
    if recipient_wallet.is_frozen:
        raise HTTPException(400, "Recipient wallet is frozen.")

    # ── KYC tier daily limit ──────────────────────────────────────────────────
    tier       = sender.verification_tier or 0
    tier_limit = TIER_LIMITS.get(tier, Decimal("0"))
    if tier_limit == Decimal("0"):
        raise HTTPException(403, "KYC verification required to send money. Complete Tier 1 KYC first.")

    if sender_wallet.limit_reset_at and sender_wallet.limit_reset_at.date() < _utcnow().date():
        sender_wallet.daily_spent = Decimal("0")

    daily_spent = sender_wallet.daily_spent or Decimal("0")
    if daily_spent + amount > tier_limit:
        remaining = tier_limit - daily_spent
        raise HTTPException(
            400,
            f"Daily limit exceeded. Remaining today: PKR {remaining:,.2f} "
            f"(Tier {tier} limit: PKR {tier_limit:,.2f})",
        )

    # ── Balance check ─────────────────────────────────────────────────────────
    if sender_wallet.balance < amount:
        raise HTTPException(
            400,
            f"Insufficient balance. Available: PKR {sender_wallet.balance:,.2f}",
        )

    # ── Large transfer — return pending token for biometric confirm ────────────
    if amount >= Decimal("1000") and not biometric_confirmed:
        payload = {
            "sender_id":    str(sender_id),
            "recipient_id": str(recipient_id),
            "amount":       str(amount),
            "purpose":      purpose,
            "description":  description or "",
            "card_id":      str(card_id) if card_id else None,
        }
        return {"status": "pending_biometric", "pending_tx_token": create_pending_tx_token(payload)}

    # ── Execute ───────────────────────────────────────────────────────────────
    return await _execute_transfer(
        db=db,
        sender_wallet=sender_wallet,
        recipient_wallet=recipient_wallet,
        sender=sender,
        recipient=recipient,
        amount=amount,
        purpose=purpose,
        description=description,
        card_id=card_id,
    )
