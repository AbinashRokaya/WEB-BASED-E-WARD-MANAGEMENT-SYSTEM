from pydantic import BaseModel, ConfigDict
from uuid import UUID
from typing import Optional


class WardResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ward_id: UUID
    ward_no: int
    ward_name: Optional[str] = None
    ward_municipality: str
    ward_district: str
    ward_province: str