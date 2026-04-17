"""Transaction schemas — PROMPT 07."""
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List, Any
from uuid import UUID

from pydantic import BaseModel, Field


# ── P2P Send ──────────────────────────────────────────────────────────────────
class SendRequest(BaseModel):
    recipient_phone: str
    amount: Decimal = Field(..., gt=0, le=2_000_000)
    purpose: str = Field("Other", pattern="^(Food|Bill|Shopping|Travel|Family|Medical|Rent|Study|Business|Salary|Zakat|Investment|Insurance|TopUp|Split|Other)$")
    description: Optional[str] = None
    pin: str = Field(..., min_length=6, max_length=6)


class SendResponse(BaseModel):
    status: str
    message: str
    reference_number: Optional[str] = None
    transaction_id: Optional[UUID] = None
    pending_tx_token: Optional[str] = None
    cashback_earned: Optional[Decimal] = None
    new_balance: Optional[Decimal] = None


class ConfirmBiometricRequest(BaseModel):
    pending_tx_token: str
    biometric_verified: bool = True


# ── QR Send ───────────────────────────────────────────────────────────────────
class QRSendRequest(BaseModel):
    qr_payload: str
    amount: Decimal = Field(..., gt=0)
    purpose: str = Field("Other")
    description: Optional[str] = None
    pin: str = Field(..., min_length=6, max_length=6)


# ── Top-up ────────────────────────────────────────────────────────────────────
class TopupRequest(BaseModel):
    phone: str
    amount: Decimal = Field(..., gt=0, le=10000)
    network: Optional[str] = None
    pin: str = Field(..., min_length=6, max_length=6)


class TopupResponse(BaseModel):
    status: str
    message: str
    network: str
    phone: str
    amount: Decimal
    reference_number: str
    new_balance: Decimal


# ── Bills ─────────────────────────────────────────────────────────────────────
class BillCategory(BaseModel):
    code: str
    name: str
    icon: str
    description: str


class BillPayRequest(BaseModel):
    category: str
    consumer_id: str
    amount: Decimal = Field(..., gt=0)
    description: Optional[str] = None
    pin: str = Field(..., min_length=6, max_length=6)


class BillPayResponse(BaseModel):
    status: str
    message: str
    reference_number: str
    consumer_id: str
    amount: Decimal
    new_balance: Decimal


# ── History ───────────────────────────────────────────────────────────────────
class TransactionItem(BaseModel):
    id: UUID
    reference_number: str
    type: str
    amount: Decimal
    fee: Decimal
    cashback_earned: Decimal
    status: str
    purpose: Optional[str]
    description: Optional[str]
    counterpart_name: Optional[str] = None
    counterpart_phone: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True


class TransactionHistoryResponse(BaseModel):
    items: List[TransactionItem]
    total: int
    page: int
    per_page: int
    has_next: bool


# ── External Wallets ──────────────────────────────────────────────────────────
class ExternalWalletLookupRequest(BaseModel):
    provider: str = Field(..., pattern="^(jazzcash|easypaisa|nayapay|upay|sadapay)$")
    phone: str


class ExternalWalletLookupResponse(BaseModel):
    found: bool
    provider: str
    phone: str
    masked_name: Optional[str] = None


class ExternalWalletSendRequest(BaseModel):
    provider: str = Field(..., pattern="^(jazzcash|easypaisa|nayapay|upay|sadapay)$")
    phone: str
    amount: Decimal = Field(..., gt=0, le=200000)
    description: Optional[str] = None
    pin: str = Field(..., min_length=6, max_length=6)


# ── External Bills ────────────────────────────────────────────────────────────
class ExternalBillFetchRequest(BaseModel):
    company: str
    consumer_id: str


class ExternalBillFetchResponse(BaseModel):
    company: str
    consumer_id: str
    customer_name: str
    amount_due: Decimal
    due_date: str
    bill_month: str


class ExternalBillPayRequest(BaseModel):
    company: str
    consumer_id: str
    amount: Decimal = Field(..., gt=0)
    pin: str = Field(..., min_length=6, max_length=6)


# ── External Bank / IBFT ──────────────────────────────────────────────────────
class ExternalBankLookupRequest(BaseModel):
    bank_name: str
    account_number: str


class ExternalBankLookupResponse(BaseModel):
    found: bool
    bank_name: str
    account_number: str
    account_title: Optional[str] = None


class ExternalBankSendRequest(BaseModel):
    bank_name: str
    account_number: str
    account_title: str
    amount: Decimal = Field(..., gt=0, le=1_000_000)
    description: Optional[str] = None
    pin: str = Field(..., min_length=6, max_length=6)
