import uuid
from sqlalchemy import Column, String, Boolean, Text, Numeric, ForeignKey, CheckConstraint, TIMESTAMP,DateTime,Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy import Enum as SAEnum
from sqlalchemy.sql import func
from database.db import Base
from model.enums import RegistrationStatus
from model.enums import GenderType, BirthKindType,ParentType,DocumentType

class BirthRegistrationModel(Base):
    __tablename__ = "birth_registration"

    registration_id      = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    registration_number  = Column(String(50), unique=True)
    ward_id              = Column(UUID(as_uuid=True), ForeignKey("ward.ward_id"), nullable=False)
    submitted_by         = Column(UUID(as_uuid=True), ForeignKey("user_account.user_id", ondelete="SET NULL"), nullable=False)
    status               = Column(SAEnum(RegistrationStatus), nullable=False, default=RegistrationStatus.DRAFT)
    rejection_reason     = Column(Text)
    created_at = Column(
        DateTime,
        server_default=func.now()
    )

    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now()
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

class ChildModel(Base):
    __tablename__ = "child"

    child_id        = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    full_name       = Column(String(100))
    gender          = Column(SAEnum(GenderType), nullable=False)
    dob_bs          = Column(String(50), nullable=False)
    time_of_birth   = Column(String)
    province        = Column(String(100))
    district        = Column(String(100))
    municipality    = Column(String(100))
    ward_no         = Column(Integer)
    tole            = Column(String(50))
    birth_kind      = Column(SAEnum(BirthKindType), nullable=False, default=BirthKindType.SINGLE)
    weight_kg       = Column(Numeric(4, 2))

    __table_args__ = (
        CheckConstraint("weight_kg IS NULL OR weight_kg > 0", name="chk_weight_positive"),
    )

class ParentModel(Base):
    __tablename__ = "parent"

    parent_id       = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    registration_id = Column(UUID(as_uuid=True), ForeignKey("birth_registration.registration_id", ondelete="CASCADE"), nullable=False)
    parent_type     = Column(SAEnum(ParentType), nullable=False)
    citizenship_no  = Column(String(50), nullable=False)
    nid_no          = Column(String(50), nullable=False)
    address_id      = Column(UUID(as_uuid=True), ForeignKey("address.address_id", ondelete="SET NULL"))
    occupation      = Column(String(100))
    nationality     = Column(String(100), nullable=False, default="NEPALESE")
    contact_no      = Column(String(50))

    
    registration = relationship("BirthRegistration", back_populates="parents")

class DocumentModel(Base):
    __tablename__ = "document"

    doc_id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    registration_id = Column(UUID(as_uuid=True), ForeignKey("birth_registration.registration_id", ondelete="CASCADE"), nullable=False)
    doc_type        = Column(SAEnum(DocumentType), nullable=False)
    file_name       = Column(String(50), nullable=False)
    file_path       = Column(String(50), nullable=False)
    mime_type       = Column(String(50))
    file_size_kb    = Column(Integer)
    notes           = Column(Text)
    created_at = Column(
        DateTime,
        server_default=func.now()
    )

    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now()
    )

    __table_args__ = (
        CheckConstraint("file_size_kb IS NULL OR file_size_kb > 0", name="chk_file_size"),
    )

    registration = relationship("BirthRegistration", back_populates="documents")

class CertificateModel(Base):
    __tablename__ = "certificate"

    cert_id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    registration_id = Column(UUID(as_uuid=True), ForeignKey("birth_registration.registration_id", ondelete="CASCADE"), nullable=False, unique=True)
    certificate_no  = Column(String(100), nullable=False, unique=True)
    nid_no          = Column(String(50))
    issued_date_bs  = Column(String(50))
    issued_date_ad  = Column(DateTime)
    issued_by       = Column(UUID(as_uuid=True), ForeignKey("user_account.user_id", ondelete="SET NULL"))
    qr_code_data    = Column(Text)
    pdf_path        = Column(Text)
    is_valid        = Column(Boolean, nullable=False, default=True)
    revoked_reason  = Column(Text)
    created_at = Column(
        DateTime,
        server_default=func.now()
    )

    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now()
    )



    __table_args__ = (
        CheckConstraint("revoked_at IS NULL OR revoked_reason IS NOT NULL", name="chk_revoked_has_reason"),
    )

    registration = relationship("BirthRegistration", back_populates="certificate")