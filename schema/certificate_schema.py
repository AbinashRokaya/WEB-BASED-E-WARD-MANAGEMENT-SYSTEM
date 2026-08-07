from pydantic import BaseModel, ConfigDict
from uuid import UUID
from datetime import datetime
from typing import Optional


class CertificateResponse(BaseModel):
    cert_id: UUID
    registration_id: UUID
    certificate_no: str
    nin_no: Optional[str] = None
    data_hash: str
    qr_path: Optional[str] = None
    pdf_path: Optional[str] = None
    is_valid: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class VerifyCertificateResponse(BaseModel):
    valid: bool
    certificate_no: str
    child_full_name: str
    register_status: str
    issued_date: datetime
    revoked_reason: Optional[str] = None
    pdf_url: Optional[str] = None