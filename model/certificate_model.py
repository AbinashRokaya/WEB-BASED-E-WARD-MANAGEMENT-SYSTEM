import uuid
from sqlalchemy import Column, String, Text, Boolean, Date, ForeignKey, CheckConstraint, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database.db import Base


class Certificate(Base):
    __tablename__ = "certificate"

    cert_id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    registration_id = Column(UUID(as_uuid=True), ForeignKey("birth_registration.registration_id", ondelete="CASCADE"), nullable=False, unique=True)
    certificate_no  = Column(String(100), nullable=False, unique=True)
    nid_no          = Column(String(50))
    issued_date_bs  = Column(String(50))
    issued_date_ad  = Column(Date)
    issued_by       = Column(UUID(as_uuid=True), ForeignKey("user_account.user_id", ondelete="SET NULL"))
    qr_code_data    = Column(Text)
    pdf_path        = Column(Text)
    is_valid        = Column(Boolean, nullable=False, default=True)
    revoked_at      = Column(TIMESTAMP(timezone=True))
    revoked_reason  = Column(Text)
    created_at      = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        CheckConstraint("revoked_at IS NULL OR revoked_reason IS NOT NULL", name="chk_revoked_has_reason"),
    )

    registration = relationship("BirthRegistration", back_populates="certificate")