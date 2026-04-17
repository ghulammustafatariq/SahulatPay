from sqlalchemy import (
    Column, String, Boolean, SmallInteger, Numeric,
    Date, DateTime, ForeignKey, CheckConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from database import Base


class SavingGoal(Base):
    __tablename__ = "saving_goals"
    __table_args__ = (
        CheckConstraint("target_amount > 0",   name="ck_goal_target_positive"),
        CheckConstraint("saved_amount >= 0",   name="ck_goal_saved_non_negative"),
    )

    id                  = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    user_id             = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    goal_name           = Column(String(255), nullable=False)
    target_amount       = Column(Numeric(12, 2), nullable=False)
    saved_amount        = Column(Numeric(12, 2), server_default="0.00")
    icon                = Column(String(10))                    # emoji character
    deadline            = Column(Date)
    is_completed        = Column(Boolean, server_default="false")
    goal_achieved       = Column(Boolean, server_default="false")   # triggers confetti in app
    withdraw_count      = Column(SmallInteger, server_default="0")  # >= 2 triggers AI roast
    # Smart auto-deduction fields
    auto_deduct_enabled = Column(Boolean, server_default="false")
    auto_deduct_amount  = Column(Numeric(10, 2))                # fixed PKR amount per cycle
    auto_deduct_freq    = Column(String(20))                    # weekly | monthly
    next_deduction_at   = Column(DateTime(timezone=True))       # APScheduler checks this every hour
    last_deduction_at   = Column(DateTime(timezone=True))       # last successful auto-deduction
    created_at          = Column(DateTime(timezone=True), server_default=func.now())
    updated_at          = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="saving_goals")
