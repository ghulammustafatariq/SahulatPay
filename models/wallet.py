from sqlalchemy import Column, Boolean, Numeric, String, DateTime, ForeignKey, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from database import Base


class Wallet(Base):
    __tablename__ = "wallets"
    __table_args__ = (
        CheckConstraint("balance >= 0.00", name="ck_wallet_balance_non_negative"),
    )

    id               = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    user_id          = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    balance          = Column(Numeric(12, 2), nullable=False, server_default="0.00")
    currency         = Column(String(3), server_default="PKR")
    is_frozen        = Column(Boolean, server_default="false")
    daily_limit      = Column(Numeric(12, 2), server_default="25000.00")
    daily_spent      = Column(Numeric(12, 2), server_default="0.00")
    limit_reset_at   = Column(DateTime(timezone=True))
    cashback_pending = Column(Numeric(10, 2), server_default="0.00")
    cashback_claimed = Column(Numeric(10, 2), server_default="0.00")
    created_at       = Column(DateTime(timezone=True), server_default=func.now())
    updated_at       = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="wallet")
