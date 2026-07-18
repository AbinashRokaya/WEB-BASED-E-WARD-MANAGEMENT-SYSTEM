import uuid
from sqlalchemy import Column, String, Integer, TIMESTAMP,ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database.db import Base
from sqlalchemy import Enum as SAEnum
from schema.ward_schema import MunicipalityType
class WardModel(Base):
    __tablename__ = "ward"

    ward_id        = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ward_name = Column(String)
    ward_no        = Column(Integer, nullable=False)
    ward_type      = Column(SAEnum(MunicipalityType), nullable=False, default=MunicipalityType.MUNICIPALITY)
    ward_municipality   = Column(String(100), nullable=False)
    ward_district       = Column(String(100), nullable=False)
    ward_province       = Column(String(50), nullable=False)

    ward_nepali_name = Column(String,default=None)
    ward_nepali_municipality   = Column(String(100), nullable=True,default=None)
    ward_nepali_district       = Column(String(100), nullable=True,default=None)
    ward_nepali_province       = Column(String(50), nullable=True,default=None)

    ward_contact_number = Column(String(50), nullable=False)
    ward_email          = Column(String(100), unique=True)
    ward_logo_path              = Column(String, nullable=True)
    chairperson_signature_path  = Column(String, nullable=True)
    chairperson_stamp_path      = Column(String, nullable=True)
    created_at     = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at     = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())

    # users               = relationship("UserModel", back_populates="ward")
    birth_registrations = relationship("BirthRegistrationModel", back_populates="ward")
    death_registrations=relationship("DeathRegistrationModel",back_populates="ward")
    migration_registrations=relationship("MigrationRegistrationModel",back_populates="ward")
    user=relationship("UserModel",back_populates="ward")
    userVerify=relationship("UserVerifyModel",back_populates="wardVerify")
    notice=relationship("NoticeModel", back_populates="ward")

