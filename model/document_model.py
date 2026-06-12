import uuid
from sqlalchemy import Column, String, Integer, Boolean, Text, ForeignKey, CheckConstraint, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy import Enum as SAEnum
from sqlalchemy.sql import func
from database.db import Base
from model.enums import DocumentType


class Document(Base):
    __tablename__ = "document"

    doc_id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    registration_id = Column(UUID(as_uuid=True), ForeignKey("birth_registration.registration_id", ondelete="CASCADE"), nullable=False)
    doc_type        = Column(SAEnum(DocumentType), nullable=False)
    file_name       = Column(String(50), nullable=False)
    file_path       = Column(String(50), nullable=False)
    mime_type       = Column(String(50))
    file_size_kb    = Column(Integer)
    uploaded_at     = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    is_verified     = Column(Boolean, nullable=False, default=False)
    verified_by     = Column(UUID(as_uuid=True), ForeignKey("user_account.user_id", ondelete="SET NULL"))
    verified_at     = Column(TIMESTAMP(timezone=True))
    notes           = Column(Text)

    __table_args__ = (
        CheckConstraint("file_size_kb IS NULL OR file_size_kb > 0", name="chk_file_size"),
    )

    registration = relationship("BirthRegistration", back_populates="documents")