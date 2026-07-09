from enum import Enum
from datetime import date
from pydantic import BaseModel
from uuid import UUID

class NoticeType(str, Enum):
    PUBLIC = "PUBLIC"
    TENDER = "TENDER"
    VACANCY = "VACANCY"
    TAX = "TAX"
    MEETING = "MEETING"
    HEALTH = "HEALTH"
    EDUCATION = "EDUCATION"
    DISASTER = "DISASTER"
    EVENT = "EVENT"
    OTHER = "OTHER"


class NoticeStatus(str, Enum):
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    EXPIRED = "EXPIRED"
    ARCHIVED = "ARCHIVED"




class NoticeCreate(BaseModel):
   
    notice_title: str
    notice_description: str
    notice_type: NoticeType
    status: NoticeStatus = NoticeStatus.DRAFT
    
    


class NoticeResponse(BaseModel):
    notice_id: UUID
    notice_ward_id: UUID
    notice_title: str
    notice_description: str
    notice_type: NoticeType
    status: NoticeStatus
    created_at: date

    class Config:
        from_attributes = True