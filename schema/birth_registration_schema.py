
from pydantic import BaseModel,ConfigDict,field_validator
from typing import Optional, List
from uuid import UUID
from model.enums import (
    BirthRegistrationStatus, GenderType, BirthKindType,
    BirthPlaceType, ParentType, RelatioshipType
)
import re
from datetime import date
NEPALI_REGEX = re.compile(
    r'^[\u0900-\u097F\s।.,()-]+$'
)
class ChildRequest(BaseModel):
    child_first_name: str
    child_middle_name: Optional[str] = None
    child_last_name: str
    child_nepali_first_name:str
    child_nepali_middle_name:Optional[str] = None
    child_nepali_last_name:str
    
    child_gender: GenderType
    child_dob_bs: date
    child_dob_ad:date
    child_time_of_birth: Optional[str] = None
    child_birth_place: BirthPlaceType = BirthPlaceType.HOSPITAL
    child_birth_kind: BirthKindType = BirthKindType.SINGLE
    child_weight_kg: Optional[int] = None

    @field_validator(
        "child_nepali_first_name",
        "child_nepali_middle_name",
        "child_nepali_last_name",
        mode="before"
    )
    @classmethod
    
    def validate_nepali_name(cls, value):
        if value is None:
            return value

        value = value.strip()

        # Allow optional empty strings
        if value == "":
            return value

        if not NEPALI_REGEX.fullmatch(value):
            raise ValueError(
                "Name must contain only Nepali (Devanagari) characters."
            )

        return value
class ChildResponse(ChildRequest):
    child_id: UUID
    registration_id: UUID
    model_config = ConfigDict(from_attributes=True)

class UpdateChildRequest(BaseModel):
    child_first_name: Optional[str] = None
    child_middle_name: Optional[str] = None
    child_last_name: Optional[str] = None
    child_nepali_first_name:Optional[str]=None
    child_nepali_middle_name:Optional[str]=None
    child_nepali_last_name:Optional[str]=None
    child_gender: Optional[GenderType] = None
    child_dob_bs: Optional[date] = None
    child_dob_ad: Optional[date] = None
    child_time_of_birth: Optional[str] = None
    child_birth_place: Optional[BirthPlaceType] = None
    child_birth_kind: Optional[BirthKindType] = None
    child_weight_kg: Optional[int] = None

    @field_validator(
        "child_nepali_first_name",
        "child_nepali_middle_name",
        "child_nepali_last_name",
        mode="before"
    )
    @classmethod
    def validate_nepali_name(cls, value):
        if value is None:
            return value

        value = value.strip()

        # Allow optional empty strings
        if value == "":
            return value

        if not NEPALI_REGEX.fullmatch(value):
            raise ValueError(
                "Name must contain only Nepali (Devanagari) characters."
            )

        return value




class ParentRequest(BaseModel):
    parent_first_name: str
    parent_middle_name: Optional[str] = None
    parent_last_name: str
    parent_nepali_first_name: Optional[str] = None
    parent_nepali_middle_name: Optional[str] = None
    parent_nepali_last_name: Optional[str] = None
    parent_type: ParentType
    parent_citizenship_no: str
    parent_nid_no: str
    parent_occupation: Optional[str] = None
    parent_nationality: str = "NEPALESE"
    parent_contact_no: Optional[str] = None

    @field_validator(
        "parent_nepali_first_name",
        "parent_nepali_middle_name",
        "parent_nepali_last_name",
        mode="before"
    )
    @classmethod
    def validate_nepali_name(cls, value):
        if value is None:
            return value

        value = value.strip()

        # Allow optional empty strings
        if value == "":
            return value

        if not NEPALI_REGEX.fullmatch(value):
            raise ValueError(
                "Name must contain only Nepali (Devanagari) characters."
            )

        return value

class ParentResponse(ParentRequest):
    parent_id: UUID
    registration_id: UUID
    model_config = ConfigDict(from_attributes=True)

class UpdateParentRequest(BaseModel):
    parent_first_name: Optional[str] = None
    parent_middle_name: Optional[str] = None
    parent_last_name: Optional[str] = None
    parent_nepali_first_name:Optional[str]=None
    parent_nepali_middle_name:Optional[str]=None
    parent_nepali_last_name:Optional[str]=None       
    
    parent_type: Optional[ParentType] = None
    parent_citizenship_no: Optional[str] = None
    parent_nid_no: Optional[str] = None
    parent_occupation: Optional[str] = None
    parent_nationality: Optional[str] = None
    parent_contact_no: Optional[str] = None

    @field_validator(
        "parent_nepali_first_name",
        "parent_nepali_middle_name",
        "parent_nepali_last_name",
        mode="before"
    )
    @classmethod
    def validate_nepali_name(cls, value):
        if value is None:
            return value

        value = value.strip()

        # Allow optional empty strings
        if value == "":
            return value

        if not NEPALI_REGEX.fullmatch(value):
            raise ValueError(
                "Name must contain only Nepali (Devanagari) characters."
            )

        return value




class NomineeRequest(BaseModel):
    nominee_first_name: str
    nominee_middle_name: Optional[str] = None
    nominee_last_name: str

    nominee_nepali_first_name: Optional[str] = None
    nominee_nepali_middle_name: Optional[str] = None
    nominee_nepali_last_name: Optional[str] = None

    nominee_citizenship_no: Optional[str] = None
    nominee_address: Optional[str] = None
    nominee_contact_no: Optional[str] = None
    nominee_witness_order: Optional[int] = None
    nominee_relationship: Optional[RelatioshipType] = None

    @field_validator(
        "nominee_nepali_first_name",
        "nominee_nepali_middle_name",
        "nominee_nepali_last_name",
        mode="before"
    )
    @classmethod
    def validate_nepali_name(cls, value):
        if value is None:
            return value

        value = value.strip()

        # Allow optional empty strings
        if value == "":
            return value

        if not NEPALI_REGEX.fullmatch(value):
            raise ValueError(
                "Name must contain only Nepali (Devanagari) characters."
            )

        return value
class NomineeResponse(NomineeRequest):
    nominee_id: UUID
    nominee_registration_id: UUID
    model_config = ConfigDict(from_attributes=True)

class UpdateNomineeRequest(BaseModel):
    nominee_first_name: Optional[str] = None
    nominee_middle_name: Optional[str] = None
    nominee_last_name: Optional[str] = None
    nominee_nepali_first_name:Optional[str]=None
    nominee_nepali_middle_name:Optional[str]=None
    nominee_nepali_last_name:Optional[str]=None
    nominee_citizenship_no: Optional[str] = None
    nominee_address: Optional[str] = None
    nominee_contact_no: Optional[str] = None
    nominee_witness_order: Optional[int] = None
    nominee_relationship: Optional[RelatioshipType] = None

    @field_validator(
        "nominee_nepali_first_name",
        "nominee_nepali_middle_name",
        "nominee_nepali_last_name",
        mode="before"
    )
    @classmethod
    def validate_nepali_name(cls, value):
        if value is None:
            return value

        value = value.strip()

        # Allow optional empty strings
        if value == "":
            return value

        if not NEPALI_REGEX.fullmatch(value):
            raise ValueError(
                "Name must contain only Nepali (Devanagari) characters."
            )

        return value


class AddressRequest(BaseModel):
    child_province: str
    child_district: str
    child_municipality: str
    child_ward_number: int
    child_tole: Optional[str] = None

class AddressResponse(AddressRequest):
    address_id: UUID
    model_config = ConfigDict(from_attributes=True)

class UpdateAddressRequest(BaseModel):
    child_province: Optional[str] = None
    child_district: Optional[str] = None
    child_municipality: Optional[str] = None
    child_ward_number: Optional[int] = None
    child_tole: Optional[str] = None

class AddressResponse(BaseModel):
    address_id: UUID
    child_province: str      # ✅ matches SQLAlchemy model
    child_district: str
    child_municipality: str
    child_ward_number: int
    child_tole: str | None = None

    model_config = ConfigDict(from_attributes=True)

class RejectRequest(BaseModel):
    reject_text: str

class RejectResponse(RejectRequest):
    reject_id: UUID
    registration_id: UUID
    model_config = ConfigDict(from_attributes=True)



class BirthRegistrationRequest(BaseModel):
    register_ward_id: UUID
    register_submitted_by: int
    child: ChildRequest
    parents: List[ParentRequest]
    nominees: List[NomineeRequest]
    address: AddressRequest

class BirthRegistrationResponse(BaseModel):
    
    register_ward_id: UUID
    register_submitted_by: int
    register_status: BirthRegistrationStatus
    child: Optional[ChildResponse] = None
    parents: Optional[List[ParentResponse]] = []
    nominees: Optional[List[NomineeResponse]] = []
    address: Optional[AddressResponse] = None
    reject: Optional[List[RejectResponse]] = []
    model_config = ConfigDict(from_attributes=True)
class UpdateRegistrationRequest(BaseModel):
    register_status: Optional[BirthRegistrationStatus] = None
    child: Optional[UpdateChildRequest] = None
    address: Optional[UpdateAddressRequest] = None

class BirthRegistrationResponseAll(BaseModel):
    registration_id: UUID
    register_ward_id: UUID
    register_submitted_by: int
    register_status: BirthRegistrationStatus

    child: Optional[ChildResponse] = None
    parents: List[ParentResponse] = []
    nominees: List[NomineeResponse] = []
    address: Optional[AddressResponse] = None
    reject: List[RejectResponse] = []

    model_config = ConfigDict(from_attributes=True)