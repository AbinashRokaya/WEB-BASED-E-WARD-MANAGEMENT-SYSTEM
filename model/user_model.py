import uuid
from sqlalchemy import Column, String, Boolean, ForeignKey, TIMESTAMP, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy import Enum as SAEnum
from sqlalchemy.sql import func
from database.db import Base
from model.enums import UserRoleType
from datetime import datetime


class UserAccount(Base):
    __tablename__ = "user_account"

    user_id       = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ward_id       = Column(UUID(as_uuid=True), ForeignKey("ward.ward_id", ondelete="SET NULL"), nullable=True)
    username      = Column(String(100), nullable=False, unique=True)
    mobile_number = Column(String(20), nullable=False)
    user_role     = Column(SAEnum(UserRoleType), nullable=False, default=UserRoleType.CITIZEN)
    full_name     = Column(String(100))
    email         = Column(String(100), unique=True)
    is_active     = Column(Boolean, nullable=False, default=True)
    created_at    = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    last_login    = Column(TIMESTAMP(timezone=True), nullable=True)

    ward                = relationship("Ward", back_populates="users")
    birth_registrations = relationship("BirthRegistration", back_populates="submitted_by_user")


class OtpCode(Base):
    __tablename__ = "otp_codes"

    otp_id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    otp_phone_number = Column(String(20), nullable=False)
    otp_code        = Column(String(6), nullable=False)
    is_used         = Column(Boolean, nullable=False, default=False)
    expires_at      = Column(DateTime, nullable=False)
    created_at      = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    
print("LOADING USER MODEL")