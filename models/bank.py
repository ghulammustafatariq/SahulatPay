from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from database import Base


class BankAccount(Base):
    __tablename__ = "bank_accounts"

    id                       = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    user_id                  = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    bank_name                = Column(String(100), nullable=False)
    account_number_encrypted = Column(String, nullable=False)       # Fernet AES-256
    account_number_masked    = Column(String(25), nullable=False)   # ****1234
    account_title            = Column(String(255), nullable=False)
    is_primary               = Column(Boolean, server_default="false")
    is_verified              = Column(Boolean, server_default="false")
    created_at               = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="bank_accounts")
