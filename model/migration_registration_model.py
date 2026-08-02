# model/migration_registration_model.py
import uuid
from sqlalchemy import Column, String, Boolean, Text, ForeignKey, DateTime, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy import Enum as SAEnum
from sqlalchemy.sql import func
from database.db import Base
from enums.migration_enum import (
    GenderType,
    RelatioshipType,
    MigrationRegistrationStatus,
    MigrationReasonType,
    MigrationAddressType,OccupationType
)


class MigrationRegistrationModel(Base):
    __tablename__ = "migration_registration"

    migration_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    register_ward_id = Column(UUID(as_uuid=True), ForeignKey("ward.ward_id"), nullable=False)
    register_submitted_by = Column(Integer, ForeignKey("users.user_id", ondelete="SET NULL"), nullable=False)
    register_status = Column(
        SAEnum(MigrationRegistrationStatus),
        nullable=False,
        default=MigrationRegistrationStatus.DRAFT,
    )

    enclosure_citizenship_copy = Column(Boolean, nullable=False, default=False)
    enclosure_address_proof = Column(Boolean, nullable=False, default=False)
    enclosure_destination_proof = Column(Boolean, nullable=False, default=False)
    enclosure_photo_count = Column(Integer, nullable=True, default=0)
    enclosure_other = Column(String(200), nullable=True)

    # --- Supporting documents — citizenship has two sides, stored
    # separately so both stay legible, same pattern as birth/death ---
    applicant_citizenship_front_path = Column(String, nullable=True)
    applicant_citizenship_back_path  = Column(String, nullable=True)
    address_proof_path               = Column(String, nullable=True)
    destination_proof_path           = Column(String, nullable=True)
    applicant_photo_path             = Column(String, nullable=True)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    ward = relationship("WardModel", back_populates="migration_registrations")
    submitted_by_user = relationship("UserModel", back_populates="migration_registrations")
    applicant = relationship("MigrationApplicantModel", back_populates="registration", uselist=False)
    addresses = relationship("MigrationAddressModel", back_populates="registration")
    migration_detail = relationship("MigrationDetailModel", back_populates="registration", uselist=False)
    family_members = relationship("MigrationFamilyMemberModel", back_populates="registration")
    certificate = relationship("MigrationCertificateModel", back_populates="registration", uselist=False)
    reject = relationship("MigrationRejectModel", back_populates="registration")


class MigrationApplicantModel(Base):
    __tablename__ = "migration_applicant"

    applicant_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    migration_id = Column(
        UUID(as_uuid=True),
        ForeignKey("migration_registration.migration_id", ondelete="CASCADE"),
        nullable=False,
    )

    applicant_full_name_np = Column(String(200), nullable=False)
    applicant_full_name_en = Column(String(200), nullable=False)
    applicant_gender = Column(SAEnum(GenderType), nullable=False)
    applicant_dob_bs = Column(String(10), nullable=False)
    applicant_dob_ad = Column(DateTime, nullable=True)
    applicant_citizenship_no = Column(String(50), nullable=False)
    applicant_nationality = Column(String(100), nullable=False, default="NEPALESE")
    aapplicant_occupation = Column(SAEnum(OccupationType), nullable=True)
    applicant_contact_no = Column(String(50))

    registration = relationship("MigrationRegistrationModel", back_populates="applicant")


class MigrationAddressModel(Base):
    __tablename__ = "migration_address"

    address_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    migration_id = Column(
        UUID(as_uuid=True),
        ForeignKey("migration_registration.migration_id", ondelete="CASCADE"),
        nullable=False,
    )

    address_type = Column(SAEnum(MigrationAddressType), nullable=False)

    province = Column(String(100))
    district = Column(String(100))
    municipality = Column(String(100))
    ward_number = Column(Integer)
    tole = Column(String(200))

    # --- Nepali equivalents, captured from the selected ward at fill-time
    # (same pattern as birth's AddressModel.ward_nepali_*) so the
    # certificate can render fully in Nepali instead of falling back to
    # the English strings typed into the cascading selects. ---
    province_np = Column(String(100), nullable=True)
    district_np = Column(String(100), nullable=True)
    municipality_np = Column(String(100), nullable=True)
    ward_name_np = Column(String(200), nullable=True)

    registration = relationship("MigrationRegistrationModel", back_populates="addresses")

class MigrationDetailModel(Base):
    __tablename__ = "migration_detail"

    migration_detail_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    migration_id = Column(
        UUID(as_uuid=True),
        ForeignKey("migration_registration.migration_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    migration_date_bs = Column(String(10), nullable=True)
    migration_date_ad = Column(DateTime, nullable=True)
    migration_reason = Column(
        SAEnum(MigrationReasonType), nullable=False, default=MigrationReasonType.OTHER
    )
    migration_reason_other = Column(String(200), nullable=True)

    registration = relationship("MigrationRegistrationModel", back_populates="migration_detail")


class MigrationFamilyMemberModel(Base):
    __tablename__ = "migration_family_member"

    family_member_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    migration_id = Column(
        UUID(as_uuid=True),
        ForeignKey("migration_registration.migration_id", ondelete="CASCADE"),
        nullable=False,
    )

    member_name_np = Column(String(200))
    member_name_en = Column(String(200))
    member_relationship = Column(SAEnum(RelatioshipType), nullable=True)
    member_gender = Column(SAEnum(GenderType), nullable=True)
    member_dob_bs = Column(String(10), nullable=True)
    member_dob_ad = Column(DateTime, nullable=True)
    member_citizenship_no = Column(String(50), nullable=True)
    member_remarks = Column(String(200), nullable=True)

    registration = relationship("MigrationRegistrationModel", back_populates="family_members")


class MigrationRejectModel(Base):
    __tablename__ = "migration_reject"

    reject_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    reject_text = Column(Text)
    migration_id = Column(
        UUID(as_uuid=True),
        ForeignKey("migration_registration.migration_id", ondelete="CASCADE"),
        nullable=False,
    )

    registration = relationship("MigrationRegistrationModel", back_populates="reject")


class MigrationCertificateModel(Base):
    __tablename__ = "migration_certificate"

    cert_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    migration_id = Column(
        UUID(as_uuid=True),
        ForeignKey("migration_registration.migration_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    certificate_no = Column(String(100), nullable=False, unique=True)
    data_hash = Column(String(64), nullable=False)
    qr_path = Column(String, nullable=True)
    pdf_path = Column(String, nullable=True)
    issued_by = Column(Integer, ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True)
    is_valid = Column(Boolean, nullable=False, default=True)
    revoked_reason = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    registration = relationship("MigrationRegistrationModel", back_populates="certificate")