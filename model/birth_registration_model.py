import uuid
from sqlalchemy import Column, String, Boolean, Text, Numeric, ForeignKey, CheckConstraint, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy import Enum as SAEnum
from sqlalchemy.sql import func
from database.db import Base
from model.enums import RegistrationStatus


class BirthRegistration(Base):
    __tablename__ = "birth_registration"

    registration_id      = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    registration_number  = Column(String(50), unique=True)
    ward_id              = Column(UUID(as_uuid=True), ForeignKey("ward.ward_id"), nullable=False)
    submitted_by         = Column(UUID(as_uuid=True), ForeignKey("user_account.user_id", ondelete="SET NULL"), nullable=False)
    is_late_registration = Column(Boolean, nullable=False, default=False)
    status               = Column(SAEnum(RegistrationStatus), nullable=False, default=RegistrationStatus.DRAFT)
    fine_amount          = Column(Numeric(10, 2), nullable=False, default=0.00)
    fine_paid            = Column(Boolean, nullable=False, default=False)
    rejection_reason     = Column(Text)
    created_at           = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at           = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    submitted_at         = Column(TIMESTAMP(timezone=True))
    verified_at          = Column(TIMESTAMP(timezone=True))
    issued_at            = Column(TIMESTAMP(timezone=True))

    __table_args__ = (
        CheckConstraint("fine_amount >= 0", name="chk_fine_non_negative"),
        CheckConstraint("fine_paid = FALSE OR is_late_registration = TRUE", name="chk_fine_paid_only_if_late"),
    )

    ward              = relationship("Ward", back_populates="birth_registrations")
    submitted_by_user = relationship("UserAccount", back_populates="birth_registrations")
    child             = relationship("Child", back_populates="registration", uselist=False)
    parents           = relationship("Parent", back_populates="registration")
    informant         = relationship("Informant", back_populates="registration", uselist=False)
    nominees          = relationship("Nominee", back_populates="registration")
    documents         = relationship("Document", back_populates="registration")
    certificate       = relationship("Certificate", back_populates="registration", uselist=False)
    workflow_logs     = relationship("WorkflowLog", back_populates="registration")