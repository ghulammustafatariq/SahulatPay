from sqlalchemy import (
    Column, String, Numeric, DateTime,
    ForeignKey, CheckConstraint, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from database import Base


class TrustedCircle(Base):
    __tablename__ = "trusted_circle"
    __table_args__ = (
        UniqueConstraint("user_id", "contact_id", name="uq_trusted_circle"),
        CheckConstraint("user_id != contact_id", name="ck_no_self_trust"),
    )

    id         = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    user_id    = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    contact_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    nickname   = Column(String(100))
    added_at   = Column(DateTime(timezone=True), server_default=func.now())

    user    = relationship("User", back_populates="trusted_circle",  foreign_keys=[user_id])
    contact = relationship("User",                                    foreign_keys=[contact_id])


class BillSplit(Base):
    __tablename__ = "bill_splits"
    __table_args__ = (
        CheckConstraint("total_amount > 0", name="ck_split_amount_positive"),
    )

    id           = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    creator_id   = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    title        = Column(String(255), nullable=False)
    total_amount = Column(Numeric(12, 2), nullable=False)
    split_type   = Column(String(20), server_default="equal")    # equal | custom
    status       = Column(String(20), server_default="active")   # active | completed | cancelled
    created_at   = Column(DateTime(timezone=True), server_default=func.now())

    creator      = relationship("User",             back_populates="bill_splits_created")
    participants = relationship("SplitParticipant", back_populates="split", cascade="all, delete-orphan")


class SplitParticipant(Base):
    __tablename__ = "split_participants"
    __table_args__ = (
        UniqueConstraint("split_id", "user_id", name="uq_split_participant"),
    )

    id               = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    split_id         = Column(UUID(as_uuid=True), ForeignKey("bill_splits.id", ondelete="CASCADE"), nullable=False)
    user_id          = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    amount           = Column(Numeric(10, 2), nullable=False)
    status           = Column(String(20), server_default="pending")  # pending | paid | declined
    paid_at          = Column(DateTime(timezone=True))
    declined_at      = Column(DateTime(timezone=True))
    reminder_sent_at = Column(DateTime(timezone=True))

    split = relationship("BillSplit", back_populates="participants")
    user  = relationship("User",      back_populates="split_participations")
