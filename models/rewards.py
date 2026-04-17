from sqlalchemy import Column, String, Boolean, Numeric, Integer, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from database import Base


class Reward(Base):
    __tablename__ = "rewards"

    id           = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    user_id      = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    total_earned = Column(Numeric(10, 2), server_default="0.00")
    pending      = Column(Numeric(10, 2), server_default="0.00")    # cashback not yet claimed
    claimed      = Column(Numeric(10, 2), server_default="0.00")    # moved to wallet
    created_at   = Column(DateTime(timezone=True), server_default=func.now())
    updated_at   = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="rewards")


class OfferTemplate(Base):
    __tablename__ = "offer_templates"

    id            = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    title         = Column(String(255), nullable=False)
    description   = Column(String)
    category      = Column(String(50),  nullable=False)     # must match transaction.purpose values
    target_amount = Column(Numeric(10, 2), nullable=False)
    reward_amount = Column(Numeric(10, 2), nullable=False)
    duration_days = Column(Integer, server_default="30")
    is_active     = Column(Boolean, server_default="true")
    created_by    = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at    = Column(DateTime(timezone=True), server_default=func.now())

    reward_offers = relationship("RewardOffer", back_populates="template")


class RewardOffer(Base):
    __tablename__ = "reward_offers"

    id            = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    user_id       = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    template_id   = Column(UUID(as_uuid=True), ForeignKey("offer_templates.id"), nullable=True)
    title         = Column(String(255), nullable=False)
    category      = Column(String(50),  nullable=False)
    target_amount = Column(Numeric(10, 2), nullable=False)
    current_spent = Column(Numeric(10, 2), server_default="0.00")  # incremented on qualifying TX
    reward_amount = Column(Numeric(10, 2), nullable=False)
    status        = Column(String(20), server_default="active")    # active | completed | claimed | expired
    expires_at    = Column(DateTime(timezone=True), nullable=False)
    completed_at  = Column(DateTime(timezone=True))
    claimed_at    = Column(DateTime(timezone=True))
    created_at    = Column(DateTime(timezone=True), server_default=func.now())

    user     = relationship("User",          back_populates="reward_offers")
    template = relationship("OfferTemplate", back_populates="reward_offers")


class RewardTransaction(Base):
    __tablename__ = "reward_transactions"

    id             = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    user_id        = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    transaction_id = Column(UUID(as_uuid=True), ForeignKey("transactions.id"), nullable=True)
    offer_id       = Column(UUID(as_uuid=True), ForeignKey("reward_offers.id"),  nullable=True)
    type           = Column(String(30), nullable=False)     # cashback | offer_reward | claim
    amount         = Column(Numeric(10, 2), nullable=False)
    created_at     = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="reward_transactions")
