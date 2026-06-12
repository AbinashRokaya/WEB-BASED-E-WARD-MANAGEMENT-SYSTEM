import uuid
from sqlalchemy import Column, String, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy import Enum as SAEnum
from database.db import Base
from model.enums import ParentType


class Parent(Base):
    __tablename__ = "parent"

    parent_id       = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    registration_id = Column(UUID(as_uuid=True), ForeignKey("birth_registration.registration_id", ondelete="CASCADE"), nullable=False)
    parent_type     = Column(SAEnum(ParentType), nullable=False)
    citizenship_no  = Column(String(50), nullable=False)
    nid_no          = Column(String(50), nullable=False)
    address_id      = Column(UUID(as_uuid=True), ForeignKey("address.address_id", ondelete="SET NULL"))
    occupation      = Column(String(100))
    nationality     = Column(String(100), nullable=False, default="NEPALESE")
    contact_no      = Column(String(50))

    __table_args__ = (
        UniqueConstraint("registration_id", "parent_type", name="uq_parent_per_registration"),
    )

    registration = relationship("BirthRegistration", back_populates="parents")