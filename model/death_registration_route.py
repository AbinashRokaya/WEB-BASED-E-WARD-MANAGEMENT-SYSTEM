import uuid
from sqlalchemy import Column, String, Boolean, Text, Numeric, ForeignKey, CheckConstraint, TIMESTAMP, DateTime, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy import Enum as SAEnum
from sqlalchemy.sql import func
from database.db import Base
from enums.death_enum import (
    GenderType, RelatioshipType,
    DeathRegistrationStatus, MaritalStatusType,
    DeathTimePeriodType, DeathPlaceType, DeathCauseType, DeathDocumentType
)
from model.ward_model import WardModel


class DeathRegistrationModel(Base):
    __tablename__ = "death_registration"

    registration_id        = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    register_ward_id       = Column(UUID(as_uuid=True), ForeignKey("ward.ward_id"), nullable=False)
    register_submitted_by  = Column(Integer, ForeignKey("users.user_id", ondelete="SET NULL"), nullable=False)
    register_status        = Column(SAEnum(DeathRegistrationStatus), nullable=False, default=DeathRegistrationStatus.DRAFT)

    # दर्ता नं. / पाना नं. — office-use box on the form
    registration_no        = Column(String(50), nullable=True)
    page_no                = Column(String(50), nullable=True)

    created_at = Column(
        DateTime,
        server_default=func.now()
    )

    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now()
    )

    ward              = relationship("WardModel", back_populates="death_registrations")
    submitted_by_user = relationship("UserModel", back_populates="death_registrations")
    deceased          = relationship("DeceasedModel", back_populates="registration", uselist=False)
    death_detail      = relationship("DeathDetailModel", back_populates="registration", uselist=False)
    informant         = relationship("InformantModel", back_populates="registration", uselist=False)
    address           = relationship("DeathAddressModel", back_populates="registration", uselist=False)
    certificate       = relationship("DeathCertificateModel", back_populates="registration", uselist=False)
    reject            = relationship("DeathRejectModel", back_populates="registration")


class DeathRejectModel(Base):
    __tablename__ = "death_reject"

    reject_id       = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    reject_text     = Column(Text)
    registration_id = Column(UUID(as_uuid=True), ForeignKey("death_registration.registration_id", ondelete="CASCADE"), nullable=False)

    registration = relationship("DeathRegistrationModel", back_populates="reject")


class DeceasedModel(Base):
    """मृतकको व्यक्तिगत विवरण — Section 1 of the form"""
    __tablename__ = "deceased"

    deceased_id      = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    registration_id  = Column(UUID(as_uuid=True), ForeignKey("death_registration.registration_id", ondelete="CASCADE"), nullable=False)

    # ख) पूरा नाम (अंग्रेजीमा)
    deceased_first_name         = Column(String(100))
    deceased_middle_name        = Column(String(100), default=None)
    deceased_last_name          = Column(String(100))

    # क) पूरा नाम (नेपालीमा)
    deceased_nepali_first_name  = Column(String(100), default=None)
    deceased_nepali_middle_name = Column(String(100), default=None)
    deceased_nepali_last_name   = Column(String(100), default=None)

    # ग) लिङ्ग
    deceased_gender   = Column(SAEnum(GenderType), nullable=False)

    # घ) जन्म मिति (वि.सं.) — form only records BS for the deceased's DOB
    deceased_dob_bs   = Column(DateTime, nullable=True)
    deceased_dob_ad   = Column(DateTime, nullable=True)

    # ङ) उमेर
    deceased_age_years  = Column(Integer)
    deceased_age_months = Column(Integer)
    deceased_age_days   = Column(Integer)

    # च) वैवाहिक स्थिति
    deceased_marital_status = Column(SAEnum(MaritalStatusType), nullable=False, default=MaritalStatusType.UNMARRIED)

    # ज) नागरिकता नं.
    deceased_citizenship_no = Column(String(50))

    # झ) पेशा
    deceased_occupation     = Column(String(100))

    # ञ) अन्य परिचय नं. (भएमा)
    deceased_other_id_no    = Column(String(50), nullable=True)

    registration = relationship("DeathRegistrationModel", back_populates="deceased")


class DeathDetailModel(Base):
    """मृत्यु सम्बन्धी विवरण — Section 2 of the form"""
    __tablename__ = "death_detail"

    death_detail_id  = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    registration_id  = Column(UUID(as_uuid=True), ForeignKey("death_registration.registration_id", ondelete="CASCADE"), nullable=False)

    # क) मृत्यु मिति (वि.सं.)
    death_date_bs    = Column(DateTime, nullable=False)

    # ख) मृत्यु समय
    death_time_period = Column(SAEnum(DeathTimePeriodType), nullable=True)
    death_time         = Column(String(20), nullable=True)

    # ग) मृत्यु स्थान — घर/अस्पताल/अन्य(खुले)
    death_place_type         = Column(SAEnum(DeathPlaceType), nullable=False, default=DeathPlaceType.HOSPITAL)
    death_place_other_detail = Column(String(200), nullable=True)

    # घ) मृत्युको कारण (चिकित्सकको राय अनुसार भएमा)
    death_cause = Column(Text, nullable=True)

    # ङ) मृत्युको प्रकार — प्राकृतिक/दुर्घटना/आत्महत्या/हत्या/अन्य(खुले)
    death_type          = Column(SAEnum(DeathCauseType), nullable=False, default=DeathCauseType.NATURAL)
    death_type_other_detail = Column(String(200), nullable=True)

    # च) मृत्यु भएको ठेगानामा मृतक बसोबास गरेको अवधि
    residence_duration_years  = Column(Integer, nullable=True)
    residence_duration_months = Column(Integer, nullable=True)
    residence_duration_days   = Column(Integer, nullable=True)

    registration = relationship("DeathRegistrationModel", back_populates="death_detail")


class InformantModel(Base):
    """जानकारी दिने व्यक्तिको विवरण — Section 3 of the form"""
    __tablename__ = "informant"

    informant_id     = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    registration_id  = Column(UUID(as_uuid=True), ForeignKey("death_registration.registration_id", ondelete="CASCADE"), nullable=False)

    # क) नाम
    informant_name          = Column(String(200), nullable=False)

    # ख) सम्बन्ध — reuses the existing RelatioshipType enum
    informant_relationship  = Column(SAEnum(RelatioshipType), nullable=True)

    # घ) सम्पर्क नं.
    informant_contact_no    = Column(String(50), nullable=True)

    # ङ) दस्तखत — declaration signature/date
    informant_signature_path = Column(String, nullable=True)
    declared_date_bs          = Column(DateTime, nullable=True)

    registration = relationship("DeathRegistrationModel", back_populates="informant")


class DeathAddressModel(Base):
    """
    Holds the three address groups on the form: the deceased's permanent
    address (छ), the place of death address (ग, within Section 2), and the
    informant's address (ग, within Section 3) — all prefixed to keep this
    in one table, the same way AddressModel does for birth registration.
    """
    __tablename__ = "death_address"

    address_id       = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    registration_id  = Column(UUID(as_uuid=True), ForeignKey("death_registration.registration_id", ondelete="CASCADE"), nullable=False)

    # छ) मृतकको स्थायी ठेगाना
    deceased_province      = Column(String)
    deceased_district      = Column(String)
    deceased_municipality  = Column(String)
    deceased_ward_number   = Column(Integer)
    deceased_tole          = Column(String)

    # ग) मृत्यु स्थान ठेगाना
    death_place_province      = Column(String)
    death_place_district      = Column(String)
    death_place_municipality  = Column(String)
    death_place_ward_number   = Column(Integer)
    death_place_tole          = Column(String)

    # ग) सूचना दिने व्यक्तिको ठेगाना
    informant_province      = Column(String)
    informant_district      = Column(String)
    informant_municipality  = Column(String)
    informant_ward_number   = Column(Integer)
    informant_tole          = Column(String)

    # Nepali ward metadata — copied from the ward record at registration
    # time (authoritative), same pattern as birth registration's AddressModel
    ward_nepali_name         = Column(String, default=None)
    ward_nepali_municipality = Column(String(100), nullable=True, default=None)
    ward_nepali_district     = Column(String(100), nullable=True, default=None)
    ward_nepali_province     = Column(String(50), nullable=True, default=None)

    registration = relationship("DeathRegistrationModel", back_populates="address")


class DeathCertificateModel(Base):
    __tablename__ = "death_certificate"

    cert_id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    registration_id  = Column(UUID(as_uuid=True), ForeignKey("death_registration.registration_id", ondelete="CASCADE"), nullable=False, unique=True)
    certificate_no   = Column(String(100), nullable=False, unique=True)
    data_hash        = Column(String(64), nullable=False)
    qr_path          = Column(String, nullable=True)
    pdf_path         = Column(String, nullable=True)
    issued_by        = Column(Integer, ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True)
    is_valid         = Column(Boolean, nullable=False, default=True)
    revoked_reason   = Column(Text, nullable=True)
    created_at       = Column(DateTime, server_default=func.now())

    registration = relationship("DeathRegistrationModel", back_populates="certificate")