from sqlalchemy import Column, SmallInteger, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from database import Base


class AiInsight(Base):
    __tablename__ = "ai_insights"

    id                 = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    user_id            = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    health_score       = Column(SmallInteger)                       # 0-100 (DeepSeek generated)
    health_label       = Column(Text)                               # Poor | Fair | Good | Excellent
    top_categories     = Column(JSONB, server_default="[]")         # [{category, amount, percentage}]
    monthly_comparison = Column(JSONB, server_default="{}")         # {thisMonth, lastMonth, change}
    savings_tips       = Column(JSONB, server_default="[]")         # ["tip1", "tip2", ...]
    unusual_spending   = Column(JSONB, server_default="[]")         # [{category, amount, note}]
    roast_content      = Column(Text)                               # AI humorous spending roast
    expires_at         = Column(DateTime(timezone=True))            # 7-day cache window
    created_at         = Column(DateTime(timezone=True), server_default=func.now())
    updated_at         = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="ai_insights")


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id         = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    user_id    = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    messages   = Column(JSONB, server_default="[]")
    # [{role:"user"|"assistant", content, type:"message"|"payment_action",
    #   amount:number|null, recipient:string|null, timestamp}]
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="chat_session")
