from pydantic import BaseModel, ConfigDict, field_validator
from typing import Optional, List
from uuid import UUID
from datetime import date
import re

from enums.migration_enum import (
    GenderType,
    RelatioshipType,
    MigrationRegistrationStatus,
    MigrationReasonType,
    MigrationAddressType,
)

NEPALI_REGEX = re.compile(r'^[\u0900-\u097F\s।.,()-]+$')


def _validate_nepali(value: Optional[str]) -> Optional[str]:
    if value is None:
        return value
    value = value.strip()
    if value == "":
        return value
    if not NEPALI_REGEX.fullmatch(value):
        raise ValueError("Name must contain only Nepali (Devanagari) characters.")
    return value


# ── Applicant ──────────────────────────────────────────────
class ApplicantRequest(BaseModel):
    applicant_full_name_np: str
    applicant_full_name_en: str
    applicant_gender: GenderType
    applicant_dob_bs: date
    applicant_dob_ad: Optional[date] = None
    applicant_citizenship_no: str
    applicant_nationality: str = "NEPALESE"
    applicant_occupation: Optional[str] = None
    applicant_contact_no: Optional[str] = None

    @field_validator("applicant_full_name_np", mode="before")
    @classmethod
    def validate_np_name(cls, value):
        return _validate_nepali(value)


class ApplicantResponse(ApplicantRequest):
    applicant_id: UUID
    migration_id: UUID
    model_config = ConfigDict(from_attributes=True)


class UpdateApplicantRequest(BaseModel):
    applicant_full_name_np: Optional[str] = None
    applicant_full_name_en: Optional[str] = None
    applicant_gender: Optional[GenderType] = None
    applicant_dob_bs: Optional[date] = None
    applicant_dob_ad: Optional[date] = None
    applicant_citizenship_no: Optional[str] = None
    applicant_nationality: Optional[str] = None
    applicant_occupation: Optional[str] = None
    applicant_contact_no: Optional[str] = None

    @field_validator("applicant_full_name_np", mode="before")
    @classmethod
    def validate_np_name(cls, value):
        return _validate_nepali(value)


# ── Address (used 3x per registration: PERMANENT / CURRENT / NEW) ──
class MigrationAddressRequest(BaseModel):
    address_type: MigrationAddressType
    province: str
    district: str
    municipality: str
    ward_number: int
    tole: Optional[str] = None


class MigrationAddressResponse(BaseModel):
    address_id: UUID
    address_type: MigrationAddressType
    province: str
    district: str
    municipality: str
    ward_number: int
    tole: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


class UpdateMigrationAddressRequest(BaseModel):
    address_type: Optional[MigrationAddressType] = None
    province: Optional[str] = None
    district: Optional[str] = None
    municipality: Optional[str] = None
    ward_number: Optional[int] = None
    tole: Optional[str] = None


# ── Migration Detail ────────────────────────────────────────
class MigrationDetailRequest(BaseModel):
    migration_date_bs: Optional[date] = None
    migration_date_ad: Optional[date] = None
    migration_reason: MigrationReasonType = MigrationReasonType.OTHER
    migration_reason_other: Optional[str] = None


class MigrationDetailResponse(MigrationDetailRequest):
    migration_detail_id: UUID
    migration_id: UUID
    model_config = ConfigDict(from_attributes=True)


class UpdateMigrationDetailRequest(BaseModel):
    migration_date_bs: Optional[date] = None
    migration_date_ad: Optional[date] = None
    migration_reason: Optional[MigrationReasonType] = None
    migration_reason_other: Optional[str] = None


# ── Family Member ───────────────────────────────────────────
class FamilyMemberRequest(BaseModel):
    member_name_np: Optional[str] = None
    member_name_en: Optional[str] = None
    member_relationship: Optional[RelatioshipType] = None
    member_gender: Optional[GenderType] = None
    member_dob_bs: Optional[date] = None
    member_dob_ad: Optional[date] = None
    member_citizenship_no: Optional[str] = None
    member_remarks: Optional[str] = None

    @field_validator("member_name_np", mode="before")
    @classmethod
    def validate_np_name(cls, value):
        return _validate_nepali(value)


class FamilyMemberResponse(FamilyMemberRequest):
    family_member_id: UUID
    migration_id: UUID
    model_config = ConfigDict(from_attributes=True)


class UpdateFamilyMemberRequest(BaseModel):
    member_name_np: Optional[str] = None
    member_name_en: Optional[str] = None
    member_relationship: Optional[RelatioshipType] = None
    member_gender: Optional[GenderType] = None
    member_dob_bs: Optional[date] = None
    member_dob_ad: Optional[date] = None
    member_citizenship_no: Optional[str] = None
    member_remarks: Optional[str] = None

    @field_validator("member_name_np", mode="before")
    @classmethod
    def validate_np_name(cls, value):
        return _validate_nepali(value)


# ── Reject ───────────────────────────────────────────────────
class RejectRequest(BaseModel):
    reject_text: str


class RejectResponse(RejectRequest):
    reject_id: UUID
    migration_id: UUID
    model_config = ConfigDict(from_attributes=True)


# ── Top-level registration ──────────────────────────────────
class MigrationRegistrationRequest(BaseModel):
    register_ward_id: UUID
    register_submitted_by: int
    applicant: ApplicantRequest
    addresses: List[MigrationAddressRequest]      # expect exactly 3: PERMANENT, CURRENT, NEW
    migration_detail: MigrationDetailRequest
    family_members: List[FamilyMemberRequest] = []

    enclosure_citizenship_copy: bool = False
    enclosure_address_proof: bool = False
    enclosure_destination_proof: bool = False
    enclosure_photo_count: Optional[int] = 0
    enclosure_other: Optional[str] = None

    @field_validator("addresses")
    @classmethod
    def validate_address_types(cls, value):
        types = {a.address_type for a in value}
        required = {
            MigrationAddressType.PERMANENT,
            MigrationAddressType.CURRENT,
            MigrationAddressType.NEW,
        }
        if types != required:
            raise ValueError(
                "addresses must contain exactly one each of PERMANENT, CURRENT and NEW"
            )
        return value


class MigrationRegistrationResponse(BaseModel):
    migration_id: UUID
    register_ward_id: UUID
    register_submitted_by: int
    register_status: MigrationRegistrationStatus

    enclosure_citizenship_copy: bool
    enclosure_address_proof: bool
    enclosure_destination_proof: bool
    enclosure_photo_count: Optional[int] = 0
    enclosure_other: Optional[str] = None

    applicant: Optional[ApplicantResponse] = None
    addresses: Optional[List[MigrationAddressResponse]] = []
    migration_detail: Optional[MigrationDetailResponse] = None
    family_members: Optional[List[FamilyMemberResponse]] = []
    reject: Optional[List[RejectResponse]] = []

    model_config = ConfigDict(from_attributes=True)


class UpdateMigrationRegistrationRequest(BaseModel):
    register_status: Optional[MigrationRegistrationStatus] = None
    applicant: Optional[UpdateApplicantRequest] = None
    migration_detail: Optional[UpdateMigrationDetailRequest] = None
    enclosure_citizenship_copy: Optional[bool] = None
    enclosure_address_proof: Optional[bool] = None
    enclosure_destination_proof: Optional[bool] = None
    enclosure_photo_count: Optional[int] = None
    enclosure_other: Optional[str] = None


class MigrationRegistrationResponseAll(BaseModel):
    migration_id: UUID
    register_ward_id: UUID
    register_submitted_by: int
    register_status: MigrationRegistrationStatus

    applicant: Optional[ApplicantResponse] = None
    addresses: List[MigrationAddressResponse] = []
    migration_detail: Optional[MigrationDetailResponse] = None
    family_members: List[FamilyMemberResponse] = []
    reject: List[RejectResponse] = []

    model_config = ConfigDict(from_attributes=True)