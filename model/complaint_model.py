# model/complaint_model.py
import uuid
from sqlalchemy import Column, String, Boolean, Text, ForeignKey, Integer, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy import Enum as SAEnum
from sqlalchemy.sql import func
from database.db import Base
from enums.complaint_enum import (
    ComplaintCategory, ComplaintPriority, ComplaintStatus, AuthorRole
)


class ComplaintModel(Base):
    __tablename__ = "complaint"

    complaint_id     = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    complaint_number = Column(String(20), unique=True, nullable=False, index=True)

    complaint_ward_id      = Column(UUID(as_uuid=True), ForeignKey("ward.ward_id"), nullable=False)
    complaint_submitted_by = Column(Integer, ForeignKey("users.user_id", ondelete="SET NULL"), nullable=False)
    complaint_assigned_to  = Column(Integer, ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True)

    complaint_category = Column(SAEnum(ComplaintCategory), nullable=False)
    complaint_status    = Column(SAEnum(ComplaintStatus), nullable=False, default=ComplaintStatus.SUBMITTED)
    complaint_priority  = Column(SAEnum(ComplaintPriority), nullable=False, default=ComplaintPriority.MEDIUM)

    subject     = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    location    = Column(String(255), nullable=True)

    # --- evidence attachments, up to 3, stored the same way death's document paths are ---
    attachment_1_path = Column(String, nullable=True)
    attachment_2_path = Column(String, nullable=True)
    attachment_3_path = Column(String, nullable=True)

    # --- resolution, set by the chairperson when closing the complaint ---
    resolution_note       = Column(Text, nullable=True)
    resolution_image_path = Column(String, nullable=True)   # ← new

    # SLA tracking — used by the escalation job
    sla_deadline = Column(DateTime, nullable=True)
    is_escalated = Column(Boolean, nullable=False, default=False)

    created_at  = Column(DateTime, server_default=func.now())
    updated_at  = Column(DateTime, server_default=func.now(), onupdate=func.now())
    resolved_at = Column(DateTime, nullable=True)

    ward              = relationship("WardModel", back_populates="complaints")
    submitted_by_user = relationship(
        "UserModel",
        foreign_keys=[complaint_submitted_by],
        back_populates="complaints"
    )

    assigned_user = relationship(
        "UserModel",
        foreign_keys=[complaint_assigned_to],
        back_populates="assigned_complaints"
    )
    remarks = relationship(
        "ComplaintRemarkModel", back_populates="complaint",
        cascade="all, delete-orphan", order_by="ComplaintRemarkModel.created_at"
    )
    reject  = relationship("ComplaintRejectModel", back_populates="complaint")


class ComplaintRejectModel(Base):
    __tablename__ = "complaint_reject"

    reject_id    = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    reject_text  = Column(Text)
    complaint_id = Column(UUID(as_uuid=True), ForeignKey("complaint.complaint_id", ondelete="CASCADE"), nullable=False)
    rejected_by  = Column(Integer, ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True)

    complaint = relationship("ComplaintModel", back_populates="reject")


class ComplaintRemarkModel(Base):
    """Comment/communication thread between citizen and staff on a complaint."""
    __tablename__ = "complaint_remark"

    remark_id    = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    complaint_id = Column(UUID(as_uuid=True), ForeignKey("complaint.complaint_id", ondelete="CASCADE"), nullable=False)

    author_id   = Column(Integer, ForeignKey("users.user_id", ondelete="SET NULL"), nullable=False)
    author_role = Column(SAEnum(AuthorRole), nullable=False)
    message     = Column(Text, nullable=False)

    is_internal = Column(Boolean, nullable=False, default=False)

    created_at = Column(DateTime, server_default=func.now())

    complaint = relationship("ComplaintModel", back_populates="remarks")