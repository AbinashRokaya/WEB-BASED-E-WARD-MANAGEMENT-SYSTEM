import uuid
from sqlalchemy import Column, String, Integer, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database.db import Base


class Ward(Base):
    __tablename__ = "ward"

    ward_id        = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ward_no        = Column(Integer, nullable=False)
    municipality   = Column(String(100), nullable=False)
    district       = Column(String(100), nullable=False)
    province       = Column(String(50), nullable=False)
    registrar_name = Column(String(150), nullable=False)
    contact_number = Column(String(50), nullable=False)
    email          = Column(String(100), unique=True)
    created_at     = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at     = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())

    users               = relationship("UserAccount", back_populates="ward")
    birth_registrations = relationship("BirthRegistration", back_populates="ward")