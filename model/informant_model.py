import uuid
from sqlalchemy import Column, String, Text, Date, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from database.db import Base


class Informant(Base):
    __tablename__ = "informant"

    informant_id    = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    registration_id = Column(UUID(as_uuid=True), ForeignKey("birth_registration.registration_id", ondelete="CASCADE"), nullable=False, unique=True)
    full_name       = Column(String(100), nullable=False)
    citizenship_no  = Column(String(50), nullable=False)
    address         = Column(Text)
    contact_no      = Column(String(20))
    reported_at_bs  = Column(String(20))
    reported_at_ad  = Column(Date)

    registration = relationship("BirthRegistration", back_populates="informant")