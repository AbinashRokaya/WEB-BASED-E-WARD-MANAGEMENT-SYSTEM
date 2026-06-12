import uuid
from sqlalchemy import Column, String, Text, SmallInteger, ForeignKey, CheckConstraint, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from database.db import Base


class Nominee(Base):
    __tablename__ = "nominee"

    nominee_id      = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    registration_id = Column(UUID(as_uuid=True), ForeignKey("birth_registration.registration_id", ondelete="CASCADE"), nullable=False)
    full_name       = Column(String(100), nullable=False)
    citizenship_no  = Column(String(50), nullable=False)
    address         = Column(Text)
    contact_no      = Column(String(20))
    witness_order   = Column(SmallInteger, nullable=False)

    __table_args__ = (
        CheckConstraint("witness_order IN (1, 2)", name="chk_witness_order"),
        UniqueConstraint("registration_id", "witness_order", name="uq_witness_per_registration"),
    )

    registration = relationship("BirthRegistration", back_populates="nominees")