from pydantic import BaseModel, ConfigDict, field_serializer, field_validator
from uuid import UUID
from typing import Optional
import enum

class MunicipalityType(str, enum.Enum):
    METROPOLITAN_CITY = "METROPOLITAN_CITY"          # महानगरपालिका
    SUB_METROPOLITAN_CITY = "SUB_METROPOLITAN_CITY"  # उपमहानगरपालिका
    MUNICIPALITY = "MUNICIPALITY"                      # नगरपालिका
    RURAL_MUNICIPALITY = "RURAL_MUNICIPALITY"          # गाउँपालिका

class WardResponse(BaseModel):
    ward_id: UUID
    ward_name: str
    ward_no: int
    ward_type: MunicipalityType
    ward_municipality: str
    ward_district: str
    ward_province: str
    ward_nepali_name: Optional[str] = None
    ward_nepali_municipality: Optional[str] = None
    ward_nepali_district: Optional[str] = None
    ward_nepali_province: Optional[str] = None
    ward_contact_number: str
    ward_email: Optional[str] = None
    ward_logo_path: Optional[str] = None
    chairperson_signature_path: Optional[str] = None
    chairperson_stamp_path: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)