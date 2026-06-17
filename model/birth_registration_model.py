import uuid
from sqlalchemy import Column, String, Boolean, Text, Numeric, ForeignKey, CheckConstraint, TIMESTAMP,DateTime,Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy import Enum as SAEnum
from sqlalchemy.sql import func
from database.db import Base
from model.enums import RegistrationStatus
from model.enums import GenderType, BirthKindType,ParentType,DocumentType,BirthPlaceType,RelatioshipType
from model.ward_model import WardModel

class BirthRegistrationModel(Base):
    __tablename__ = "birth_registration"

    registration_id      =          Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    register_ward_id              = Column(UUID(as_uuid=True), ForeignKey("ward.ward_id"), nullable=False)
    register_submitted_by         = Column(Integer, ForeignKey("users.user_id", ondelete="SET NULL"), nullable=False)
    register_status               = Column(SAEnum(RegistrationStatus), nullable=False, default=RegistrationStatus.DRAFT)
    created_at = Column(
        DateTime,
        server_default=func.now()
    )

    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now()
    )



    ward              = relationship("WardModel", back_populates="birth_registrations")
    submitted_by_user = relationship("UserModel", back_populates="birth_registrations")
    child             = relationship("ChildModel", back_populates="registration", uselist=False)
    parents           = relationship("ParentModel", back_populates="registration")
    nominees          = relationship("NomineeModel", back_populates="registration")
    reject = relationship("RejectModel",back_populates="registration")
    address = relationship("AddressModel",back_populates="registration")


    # informant         = relationship("Informant", back_populates="registration", uselist=False)
    # documents         = relationship("Document", back_populates="registration")
    # certificate       = relationship("Certificate", back_populates="registration", uselist=False)
    # workflow_logs     = relationship("WorkflowLog", back_populates="registration")
class RejectModel(Base):
    __tablename__ = "reject"

    reject_id = Column(UUID(as_uuid=True),primary_key=True,default=uuid.uuid4)
    reject_text=Column(Text)
    registration_id = Column(UUID(as_uuid=True), ForeignKey("birth_registration.registration_id", ondelete="CASCADE"), nullable=False)

    registration = relationship("BirthRegistrationModel", back_populates="reject")

class ChildModel(Base):
    __tablename__ = "child"

    child_id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    registration_id = Column(UUID(as_uuid=True), ForeignKey("birth_registration.registration_id", ondelete="CASCADE"), nullable=False)
    child_first_name       = Column(String(100))

    child_middle_name     = Column(String(100),default=None)
    child_last_name        =Column(String(100))
    child_gender          = Column(SAEnum(GenderType), nullable=False)
    child_dob_bs          = Column(String(50), nullable=False)
    child_time_of_birth   = Column(String)
    child_birth_place     = Column(SAEnum(BirthPlaceType),default=BirthPlaceType.HOSPITAL)
    child_birth_kind      = Column(SAEnum(BirthKindType), nullable=False, default=BirthKindType.SINGLE)
    child_weight_kg       = Column(Integer)

    registration = relationship("BirthRegistrationModel", back_populates="child")

   

class ParentModel(Base):
    __tablename__ = "parent"

    parent_id       = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    registration_id = Column(UUID(as_uuid=True), ForeignKey("birth_registration.registration_id", ondelete="CASCADE"), nullable=False)
    parent_first_name       = Column(String(100))

    parent_middle_name     = Column(String(100),default=None)
    parent_last_name        =Column(String(100))
    parent_type     = Column(SAEnum(ParentType), nullable=False)
    parrent_citizenship_no  = Column(String(50), nullable=False)
    parent_nid_no          = Column(String(50), nullable=False)
    # parent_address_id      = Column(UUID(as_uuid=True), ForeignKey("address.address_id", ondelete="SET NULL"))
    parent_occupation      = Column(String(100))
    parent_nationality     = Column(String(100), nullable=False, default="NEPALESE")
    parent_contact_no      = Column(String(50))

    
    registration = relationship("BirthRegistrationModel", back_populates="parents")

# class DocumentModel(Base):
#     __tablename__ = "document"

#     doc_id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
#     # registration_id = Column(UUID(as_uuid=True), ForeignKey("birth_registration.registration_id", ondelete="CASCADE"), nullable=False)
#     doc_type        = Column(SAEnum(DocumentType), nullable=False)
#     file_name       = Column(String(50), nullable=False)
#     file_path       = Column(String(50), nullable=False)
#     mime_type       = Column(String(50))
#     file_size_kb    = Column(Integer)
#     notes           = Column(Text)
#     created_at = Column(
#         DateTime,
#         server_default=func.now()
#     )

#     updated_at = Column(
#         DateTime,
#         server_default=func.now(),
#         onupdate=func.now()
#     )

#     __table_args__ = (
#         CheckConstraint("file_size_kb IS NULL OR file_size_kb > 0", name="chk_file_size"),
#     )

    # registration = relationship("BirthRegistrationModelModelModel", back_populates="documents")

# class CertificateModel(Base):
#     __tablename__ = "certificate"

#     cert_id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
#     # registration_id = Column(UUID(as_uuid=True), ForeignKey("birth_registration.registration_id", ondelete="CASCADE"), nullable=False, unique=True)
#     certificate_no  = Column(String(100), nullable=False, unique=True)
#     nid_no          = Column(String(50))
#     issued_date_bs  = Column(String(50))
#     issued_date_ad  = Column(DateTime)
#     issued_by       = Column(UUID(as_uuid=True), ForeignKey("user_account.user_id", ondelete="SET NULL"))
#     qr_code_data    = Column(Text)
#     pdf_path        = Column(Text)
#     is_valid        = Column(Boolean, nullable=False, default=True)
#     revoked_reason  = Column(Text)
#     created_at = Column(
#         DateTime,
#         server_default=func.now()
#     )

#     updated_at = Column(
#         DateTime,
#         server_default=func.now(),
#         onupdate=func.now()
#     )



#     __table_args__ = (
#         CheckConstraint("revoked_at IS NULL OR revoked_reason IS NOT NULL", name="chk_revoked_has_reason"),
#     )

    # registration = relationship("BirthRegistrationModelModelModel", back_populates="certificate")

class NomineeModel(Base):
    __tablename__ = "nominee"

    nominee_id      = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nominee_registration_id = Column(UUID(as_uuid=True), ForeignKey("birth_registration.registration_id"))
    nominee_first_name       = Column(String(100))
    nominee_middle_name=Column(String(100),default=None)
    nominee_last_name=Column(String(100))
    nominee_citizenship_no  = Column(String(50))
    nominee_address         = Column(Text)
    nominee_contact_no      = Column(String(20))
    nominee_witness_order   = Column(Integer)
    nominee_relationship=Column(SAEnum(RelatioshipType))

    registration    = relationship("BirthRegistrationModel", back_populates="nominees")


class AddressModel(Base):
    __tablename__="address"

    address_id=Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    registration_id = Column(UUID(as_uuid=True), ForeignKey("birth_registration.registration_id", ondelete="CASCADE"), nullable=False)

    child_province = Column(String)
    child_district = Column(String)
    child_municipality = Column(String)
    child_ward_number = Column(Integer)
    child_tole=Column(String)

    registration    = relationship("BirthRegistrationModel", back_populates="address")
