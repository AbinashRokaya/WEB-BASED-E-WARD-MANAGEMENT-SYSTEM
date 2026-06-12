import uuid
from sqlalchemy import Column, String, Integer, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from database.db import Base


class Address(Base):
    __tablename__ = "address"

    address_id   = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    province     = Column(String(50), nullable=False)
    district     = Column(String(50), nullable=False)
    municipality = Column(String(100), nullable=False)
    ward_no      = Column(Integer, nullable=False)
    tole         = Column(String(30), nullable=False)
    created_at   = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())