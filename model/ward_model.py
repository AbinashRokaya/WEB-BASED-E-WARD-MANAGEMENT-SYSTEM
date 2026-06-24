import uuid
from sqlalchemy import Column, String, Integer, TIMESTAMP,ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database.db import Base


class WardModel(Base):
    __tablename__ = "ward"

    ward_id        = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ward_name = Column(String)
    ward_no        = Column(Integer, nullable=False)
    ward_municipality   = Column(String(100), nullable=False)
    ward_district       = Column(String(100), nullable=False)
    ward_province       = Column(String(50), nullable=False)
   
    ward_contact_number = Column(String(50), nullable=False)
    ward_email          = Column(String(100), unique=True)
    created_at     = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at     = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())

    # users               = relationship("UserModel", back_populates="ward")
    birth_registrations = relationship("BirthRegistrationModel", back_populates="ward")
    user=relationship("UserModel",back_populates="ward")
    userVerify=relationship("UserVerifyModel",back_populates="wardVerify")

