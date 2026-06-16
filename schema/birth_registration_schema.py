try:
    from pydantic import BaseModel, field_validator
except Exception:
    from pydantic import BaseModel
    from pydantic import validator as field_validator
import re
import uuid
from datetime import datetime
from typing import List, Optional

from model.enums import (
    RegistrationStatus,
    GenderType,
    BirthKindType,
    ParentType,
    BirthPlaceType,
    RelatioshipType,
)

provience_list=["Koshi", "Madhesh", "Bagmati", "Gandaki", "Lumbini", "Karnali", "Sudurpashchim"]

class AddressRequest(BaseModel):
    child_provience: str
    child_district: str
    child_municipality: str
    child_ward_number: int
    child_tole: str

    @field_validator("child_ward_number")
    def validate_ward_number(cls, value):
        if value < 1 or value > 32:
            raise ValueError("Ward number must be between 1 and 32")
        return value

    @field_validator("child_provience")
    def validate_provience(cls, value):
        if value not in provience_list:
            raise ValueError(f"Provience must be one of the following: {', '.join(provience_list)}")
        return value

class AddressResponse(BaseModel):
    address_id = uuid.UUID
    
class ChildRequest(BaseModel):
    child_first_name: str
    child_middle_name: Optional[str] = None
    child_last_name: str
    child_gender: GenderType
    child_dob_bs: str
    child_time_of_birth: Optional[str] = None
    child_birth_place: BirthPlaceType = BirthPlaceType.HOSPITAL
    child_birth_kind: BirthKindType = BirthKindType.SINGLE
    child_weight_kg: Optional[int] = None
    
    @field_validator("child_dob_bs")
    def validate_child_dob_bs(cls,value):
        if not re.fullmatch(r'^\d{4}-\d{2}-\d{2}$', value):
            raise ValueError("Date of birth (BS) must be in YYYY-MM-DD format")
        return value
    
    @field_validator("child_weight_kg")
    def validate_child_weight_kg(cls,value):
        if value is not None and value <= 0:
                raise ValueError("Birth weight must be a positive number")
        return value

class ChildResponse(BaseModel):
    child_id=uuid.UUID
    registration_id=uuid.UUID

class ParentRequest(BaseModel):
    parent_first_name: str
    parent_middle_name: Optional[str] = None
    parent_last_name: str
    parent_type: ParentType
    parent_citizenship_no: str
    parent_nid_no: str
    parent_occupation: Optional[str] = None
    parent_nationality: str = "NEPALESE"
    parent_contact_no: Optional[str] = None

    @field_validator("parent_contact_no")
    def validate_contact_no(cls, value):
        if value is not None and not re.fullmatch(r'^(98|97)\d{8}$', value):
            raise ValueError("Contact number must be a valid Nepali mobile number")
        return value

    @field_validator("parent_citizenship_no")
    def validate_citizenship_no(cls, value):
        if not re.fullmatch(r'^[\d-]{5,30}$', value):
            raise ValueError("Citizenship number must contain only digits and hyphens")
        return value

    @field_validator("parent_nid_no")
    def validate_nid_no(cls, value):
        if not re.fullmatch(r'^\d{10}$', value):
            raise ValueError("National ID number must be a 10-digit number")
        return value
    
class ParentResponse(ParentRequest):
    parent_id: uuid.UUID
    registration_id: uuid.UUID

class NomineeRequest(BaseModel):
    nominee_first_name: str
    nominee_middle_name: Optional[str] = None
    nominee_last_name: str
    nominee_citizenship_no: Optional[str] = None
    nominee_address: Optional[str] = None
    nominee_contact_no: Optional[str] = None
    nominee_witness_order: int
    nominee_relationship: RelatioshipType

    @field_validator("nominee_contact_no")
    def validate_contact_no(cls, value):
        if value is not None and not re.fullmatch(r'^(98|97)\d{8}$', value):
            raise ValueError("Contact number must be a valid Nepali mobile number")
        return value

    @field_validator("nominee_witness_order")
    def validate_witness_order(cls, value):
        if value not in (1, 2):
            raise ValueError("Witness order must be 1 or 2")
        return value


class NomineeResponse(NomineeRequest):
    nominee_id: uuid.UUID
    nominee_registration_id: uuid.UUID


class RejectRequest(BaseModel):
    reject_text: str


class RejectResponse(RejectRequest):
    reject_id: uuid.UUID
    registration_id: uuid.UUID


class BirthRegistrationRequest(BaseModel):
    register_ward_id: uuid.UUID
    child: ChildRequest
    parents: List[ParentRequest]
    nominees: List[NomineeRequest]
    address: AddressRequest

    @field_validator("parents")
    def validate_parents(cls, value):
        if len(value) < 1:
            raise ValueError("At least one parent must be provided")
        return value

    @field_validator("nominees")
    def validate_nominees(cls, value):
        if len(value) != 2:
            raise ValueError("Exactly two nominees (witnesses) are required")
        orders = sorted(n.nominee_witness_order for n in value)
        if orders != [1, 2]:
            raise ValueError("Nominees must have witness orders 1 and 2 with no duplicates")
        return value


class BirthRegistrationResponse(BaseModel):
    registration_id: uuid.UUID
    register_ward_id: uuid.UUID
    register_submitted_by: int
    register_status: RegistrationStatus
    created_at: datetime
    updated_at: datetime
    child: Optional[ChildResponse] = None
    parents: List[ParentResponse] = []
    nominees: List[NomineeResponse] = []
    address: Optional[AddressResponse] = None
    reject: List[RejectResponse] = []


class BirthRegistrationSummaryResponse(BaseModel):
    registration_id: uuid.UUID
    register_status: RegistrationStatus
    created_at: datetime
    child_first_name: Optional[str] = None
    child_last_name: Optional[str] = None


class RegistrationStatusUpdateRequest(BaseModel):
    register_status: RegistrationStatus
    reject_text: Optional[str] = None
           