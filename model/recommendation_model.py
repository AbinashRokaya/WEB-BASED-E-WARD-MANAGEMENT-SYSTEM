# model/recommendation_model.py
import uuid
from sqlalchemy import Column, String, Text, ForeignKey, DateTime, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy import Enum as SAEnum
from sqlalchemy.sql import func
from database.db import Base
from enums.recommendation_enum import RecommendationLetterType, RecommendationStatus


class RecommendationLetterModel(Base):
    __tablename__ = "recommendation_letter"

    letter_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # FK to the ward table — set from the applicant's selected ward
    # (province/district/municipality/ward dropdown), same as
    # BirthRegistrationModel.register_ward_id. This used to be
    # auto-assigned from the submitting officer's own ward; it is now
    # explicitly chosen on the form, matching birth registration.
    register_ward_id = Column(UUID(as_uuid=True), ForeignKey("ward.ward_id"), nullable=False)
    register_submitted_by = Column(Integer, ForeignKey("users.user_id", ondelete="SET NULL"), nullable=False)
    register_status = Column(SAEnum(RecommendationStatus), nullable=False, default=RecommendationStatus.DRAFT)

    letter_type = Column(SAEnum(RecommendationLetterType), nullable=False)
    letter_type_other = Column(String(200), nullable=True)   # used when letter_type == OTHER

    applicant_full_name_np = Column(String(200), nullable=False)
    applicant_full_name_en = Column(String(200), nullable=False)
    applicant_citizenship_no = Column(String(50), nullable=False)
    applicant_contact_no = Column(String(50), nullable=True)

    # English selection, snapshotted at submission time
    applicant_province = Column(String(100))
    applicant_district = Column(String(100))
    applicant_municipality = Column(String(100))
    applicant_ward_number = Column(Integer)
    applicant_tole = Column(String(200))

    # Nepali labels for the same ward, snapshotted at submission time —
    # mirrors BirthRegistration's ward_nepali_* address fields so the
    # printed letter can render fully in Nepali without re-joining
    # against the ward table.
    ward_nepali_province = Column(String(100), nullable=True)
    ward_nepali_district = Column(String(100), nullable=True)
    ward_nepali_municipality = Column(String(100), nullable=True)
    ward_nepali_name = Column(String(100), nullable=True)
    ward_type = Column(String(50), nullable=True)

    purpose = Column(Text, nullable=False)   # why they need this letter — shown on the printed letter

    # --- citizenship is two-sided, stored separately so both stay legible,
    #     same pattern as DeathRegistrationModel's deceased_citizenship_*_path ---
    applicant_citizenship_front_path = Column(String, nullable=True)
    applicant_citizenship_back_path = Column(String, nullable=True)

    # which document this is (land ownership cert, income proof, etc.)
    # depends on letter_type — see SUPPORTING_DOCUMENT_REQUIRED in the router
    supporting_document_path = Column(String, nullable=True)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    ward = relationship("WardModel", back_populates="recommendation_letters")
    submitted_by_user = relationship("UserModel", back_populates="recommendation_letters")
    certificate = relationship("RecommendationCertificateModel", back_populates="letter", uselist=False)
    reject = relationship("RecommendationRejectModel", back_populates="letter")


class RecommendationRejectModel(Base):
    __tablename__ = "recommendation_reject"

    reject_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    reject_text = Column(Text)
    letter_id = Column(UUID(as_uuid=True), ForeignKey("recommendation_letter.letter_id", ondelete="CASCADE"), nullable=False)

    letter = relationship("RecommendationLetterModel", back_populates="reject")


from sqlalchemy import Boolean  # add to your existing import line

class RecommendationCertificateModel(Base):
    __tablename__ = "recommendation_certificate"

    cert_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    letter_id = Column(UUID(as_uuid=True), ForeignKey("recommendation_letter.letter_id", ondelete="CASCADE"), nullable=False, unique=True)
    certificate_no = Column(String(100), nullable=False, unique=True)
    data_hash = Column(String(64), nullable=False)
    qr_path = Column(String, nullable=True)
    pdf_path = Column(String, nullable=True)
    issued_by = Column(Integer, ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True)
    is_valid = Column(Boolean, nullable=False, default=True)
    revoked_reason = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    letter = relationship("RecommendationLetterModel", back_populates="certificate")