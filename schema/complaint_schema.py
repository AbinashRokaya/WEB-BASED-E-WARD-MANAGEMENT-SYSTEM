# schema/complaint_schema.py
from pydantic import BaseModel, ConfigDict, constr
from typing import Optional, List
from uuid import UUID
from datetime import datetime
from enums.complaint_enum import ComplaintCategory, ComplaintPriority, ComplaintStatus, AuthorRole


# ══════════════════════════════════════════════
# Reject
# ══════════════════════════════════════════════

class ComplaintRejectRequest(BaseModel):
    reject_text: constr(min_length=10, max_length=1000)


class ComplaintRejectResponse(BaseModel):
    reject_id: UUID
    complaint_id: UUID
    reject_text: str
    rejected_by: Optional[int] = None
    model_config = ConfigDict(from_attributes=True)


# ══════════════════════════════════════════════
# Remarks (comment thread)
# ══════════════════════════════════════════════

class RemarkCreateRequest(BaseModel):
    message: constr(min_length=1, max_length=1000)
    is_internal: bool = False


class RemarkResponse(BaseModel):
    remark_id: UUID
    complaint_id: UUID
    author_id: int
    author_role: AuthorRole
    message: str
    is_internal: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ══════════════════════════════════════════════
# Update — generic field-level update
# ══════════════════════════════════════════════

class UpdateComplaintRequest(BaseModel):
    complaint_status: Optional[ComplaintStatus] = None
    complaint_category: Optional[ComplaintCategory] = None
    complaint_priority: Optional[ComplaintPriority] = None
    complaint_assigned_to: Optional[int] = None
    subject: Optional[str] = None
    description: Optional[str] = None
    location: Optional[str] = None
    resolution_note: Optional[str] = None


# ══════════════════════════════════════════════
# Documents
# ══════════════════════════════════════════════

class ComplaintDocumentsResponse(BaseModel):
    attachment_1_path: Optional[str] = None
    attachment_2_path: Optional[str] = None
    attachment_3_path: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


# ══════════════════════════════════════════════
# Complaint (top level)
# ══════════════════════════════════════════════

class ComplaintResponse(BaseModel):
    complaint_id: UUID
    complaint_number: str
    complaint_ward_id: UUID
    complaint_submitted_by: int
    complaint_assigned_to: Optional[int] = None

    complaint_category: ComplaintCategory
    complaint_status: ComplaintStatus
    complaint_priority: ComplaintPriority

    subject: str
    description: str
    location: Optional[str] = None
    resolution_note: Optional[str] = None
    resolution_image_path: Optional[str] = None   # ← new

    attachment_1_path: Optional[str] = None
    attachment_2_path: Optional[str] = None
    attachment_3_path: Optional[str] = None

    created_at: datetime
    updated_at: datetime
    resolved_at: Optional[datetime] = None

    remarks: List[RemarkResponse] = []
    reject: List[ComplaintRejectResponse] = []

    model_config = ConfigDict(from_attributes=True)


class ComplaintResponseAll(BaseModel):
    """Lightweight shape for list/table views."""
    complaint_id: UUID
    complaint_number: str
    complaint_ward_id: UUID
    complaint_submitted_by: int

    complaint_category: ComplaintCategory
    complaint_status: ComplaintStatus
    complaint_priority: ComplaintPriority

    subject: str
    created_at: datetime

    resolution_note: Optional[str] = None          # ← new
    resolution_image_path: Optional[str] = None    # ← new

    reject: List[ComplaintRejectResponse] = []

    model_config = ConfigDict(from_attributes=True)


class ComplaintStatsResponse(BaseModel):
    total: int
    by_status: dict
    by_category: dict
    escalated: int