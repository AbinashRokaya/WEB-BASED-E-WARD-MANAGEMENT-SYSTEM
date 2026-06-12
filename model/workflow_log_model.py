import uuid
from sqlalchemy import Column, String, Text, ForeignKey, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database.db import Base


class WorkflowLog(Base):
    __tablename__ = "workflow_log"

    log_id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    registration_id = Column(UUID(as_uuid=True), ForeignKey("birth_registration.registration_id", ondelete="CASCADE"), nullable=False)
    action          = Column(String(100), nullable=False)
    status_from     = Column(String(50))
    status_to       = Column(String(50))
    performed_by    = Column(UUID(as_uuid=True), ForeignKey("user_account.user_id", ondelete="SET NULL"))
    notes           = Column(Text)
    created_at      = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())

    registration = relationship("BirthRegistration", back_populates="workflow_logs")