import uuid
from sqlalchemy import Column, String, Integer, Date, Time, Numeric, ForeignKey, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy import Enum as SAEnum
from database.db import Base
from model.enums import GenderType, BirthKindType


class Child(Base):
    __tablename__ = "child"

    child_id        = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    registration_id = Column(UUID(as_uuid=True), ForeignKey("birth_registration.registration_id", ondelete="CASCADE"), nullable=False, unique=True)
    full_name       = Column(String(100))
    gender          = Column(SAEnum(GenderType), nullable=False)
    dob_bs          = Column(String(50), nullable=False)
    dob_ad          = Column(Date, nullable=False)
    time_of_birth   = Column(Time)
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

    registration = relationship("BirthRegistration", back_populates="child")