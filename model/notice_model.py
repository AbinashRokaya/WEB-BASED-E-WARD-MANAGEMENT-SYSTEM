from datetime import date
from sqlalchemy import Column,INTEGER,String, Text, Date, Enum, Boolean,TIMESTAMP,ForeignKey

from sqlalchemy.orm import Mapped, mapped_column,relationship

from database.db import Base
from schema.notice_schema import NoticeType, NoticeStatus
import uuid
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

class NoticeModel(Base):
    __tablename__ = "notices"

    notice_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    notice_title = Column(String(255), nullable=False)
    notice_description = Column(Text)
    notice_ward_id = Column(UUID(as_uuid=True), ForeignKey("ward.ward_id"), nullable=False)
    notice_type = Column(Enum(NoticeType), default=NoticeType.PUBLIC)
    notice_status = Column(Enum(NoticeStatus), default=NoticeStatus.DRAFT)

    # was: notice_image_path — renamed to match schema/router/frontend
    notice_attachment_path = Column(String, nullable=True)  # relative to /static, e.g. "notices/{notice_id}/file_xxx.png"
    notice_attachment_type = Column(String, nullable=True)

    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    ward = relationship("WardModel", back_populates="notice")