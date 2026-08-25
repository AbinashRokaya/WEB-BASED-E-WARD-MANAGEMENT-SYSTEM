from pydantic import BaseModel, ConfigDict, field_validator
from typing import Optional, List
from uuid import UUID
from enums.death_enum import (
    DeathRegistrationStatus, GenderType, MaritalStatusType,
    DeathTimePeriodType, DeathPlaceType, DeathCauseType, RelatioshipType
)
from schema.ward_schema import MunicipalityType
import re
from datetime import date

NEPALI_REGEX = re.compile(
    r'^[\u0900-\u097F\s।.,()-]+$'
)


def empty_str_to_none(value):
    """Shared coercion for Optional[int] fields fed by form/text inputs.
    A blank <input type="number"> (or any left-empty field) submits as
    the string '' in the multipart/JSON payload, not as null/omitted —
    Pydantic's int parser rejects '' outright, which is what was causing
    the 422 on death_age_years/months/days. Any Optional[int] field in
    this file that can come from a blank form field needs this applied
    via a `mode="before"` field_validator, or it will hit the exact same
    error the moment a user leaves it empty."""
    if value is None:
        return None
    if isinstance(value, str) and value.strip() == "":
        return None
    return value


# ══════════════════════════════════════════════
# Deceased (मृतकको व्यक्तिगत विवरण)
# ══════════════════════════════════════════════

class DeceasedRequest(BaseModel):
    deceased_first_name: str
    deceased_middle_name: Optional[str] = None
    deceased_last_name: str
    deceased_nepali_first_name: Optional[str] = None
    deceased_nepali_middle_name: Optional[str] = None
    deceased_nepali_last_name: Optional[str] = None

    deceased_gender: GenderType
    deceased_dob_bs: Optional[date] = None
    deceased_dob_ad: Optional[date] = None

    deceased_age_years: Optional[int] = None
    deceased_age_months: Optional[int] = None
    deceased_age_days: Optional[int] = None

    deceased_marital_status: MaritalStatusType = MaritalStatusType.UNMARRIED
    deceased_citizenship_no: Optional[str] = None
    deceased_occupation: Optional[str] = None
    deceased_other_id_no: Optional[str] = None

    @field_validator(
        "deceased_age_years",
        "deceased_age_months",
        "deceased_age_days",
        mode="before"
    )
    @classmethod
    def validate_age_fields(cls, value):
        return empty_str_to_none(value)

    @field_validator(
        "deceased_nepali_first_name",
        "deceased_nepali_middle_name",
        "deceased_nepali_last_name",
        mode="before"
    )
    @classmethod
    def validate_nepali_name(cls, value):
        if value is None:
            return value
        value = value.strip()
        if value == "":
            return value
        if not NEPALI_REGEX.fullmatch(value):
            raise ValueError(
                "Name must contain only Nepali (Devanagari) characters."
            )
        return value


class DeceasedResponse(DeceasedRequest):
    deceased_id: UUID
    registration_id: UUID
    model_config = ConfigDict(from_attributes=True)


class UpdateDeceasedRequest(BaseModel):
    deceased_first_name: Optional[str] = None
    deceased_middle_name: Optional[str] = None
    deceased_last_name: Optional[str] = None
    deceased_nepali_first_name: Optional[str] = None
    deceased_nepali_middle_name: Optional[str] = None
    deceased_nepali_last_name: Optional[str] = None
    deceased_gender: Optional[GenderType] = None
    deceased_dob_bs: Optional[date] = None
    deceased_dob_ad: Optional[date] = None
    deceased_age_years: Optional[int] = None
    deceased_age_months: Optional[int] = None
    deceased_age_days: Optional[int] = None
    deceased_marital_status: Optional[MaritalStatusType] = None
    deceased_citizenship_no: Optional[str] = None
    deceased_occupation: Optional[str] = None
    deceased_other_id_no: Optional[str] = None

    @field_validator(
        "deceased_age_years",
        "deceased_age_months",
        "deceased_age_days",
        mode="before"
    )
    @classmethod
    def validate_age_fields(cls, value):
        return empty_str_to_none(value)

    @field_validator(
        "deceased_nepali_first_name",
        "deceased_nepali_middle_name",
        "deceased_nepali_last_name",
        mode="before"
    )
    @classmethod
    def validate_nepali_name(cls, value):
        if value is None:
            return value
        value = value.strip()
        if value == "":
            return value
        if not NEPALI_REGEX.fullmatch(value):
            raise ValueError(
                "Name must contain only Nepali (Devanagari) characters."
            )
        return value


# ══════════════════════════════════════════════
# Death detail (मृत्यु सम्बन्धी विवरण)
# ══════════════════════════════════════════════

class DeathDetailRequest(BaseModel):
    death_date_bs: date
    death_time_period: Optional[DeathTimePeriodType] = None
    death_time: Optional[str] = None

    death_place_type: DeathPlaceType = DeathPlaceType.HOSPITAL
    death_place_other_detail: Optional[str] = None

    death_cause: Optional[str] = None

    death_type: DeathCauseType = DeathCauseType.NATURAL
    death_type_other_detail: Optional[str] = None

    residence_duration_years: Optional[int] = None
    residence_duration_months: Optional[int] = None
    residence_duration_days: Optional[int] = None

    @field_validator(
        "residence_duration_years",
        "residence_duration_months",
        "residence_duration_days",
        mode="before"
    )
    @classmethod
    def validate_residence_duration_fields(cls, value):
        return empty_str_to_none(value)


class DeathDetailResponse(DeathDetailRequest):
    death_detail_id: UUID
    registration_id: UUID
    model_config = ConfigDict(from_attributes=True)


class UpdateDeathDetailRequest(BaseModel):
    death_date_bs: Optional[date] = None
    death_time_period: Optional[DeathTimePeriodType] = None
    death_time: Optional[str] = None
    death_place_type: Optional[DeathPlaceType] = None
    death_place_other_detail: Optional[str] = None
    death_cause: Optional[str] = None
    death_type: Optional[DeathCauseType] = None
    death_type_other_detail: Optional[str] = None
    residence_duration_years: Optional[int] = None
    residence_duration_months: Optional[int] = None
    residence_duration_days: Optional[int] = None

    @field_validator(
        "residence_duration_years",
        "residence_duration_months",
        "residence_duration_days",
        mode="before"
    )
    @classmethod
    def validate_residence_duration_fields(cls, value):
        return empty_str_to_none(value)


# ══════════════════════════════════════════════
# Informant (जानकारी दिने व्यक्तिको विवरण)
# ══════════════════════════════════════════════

class InformantRequest(BaseModel):
    informant_name: str
    informant_relationship: Optional[RelatioshipType] = None
    informant_contact_no: Optional[str] = None
    informant_signature_path: Optional[str] = None
    declared_date_bs: Optional[date] = None


class InformantResponse(InformantRequest):
    informant_id: UUID
    registration_id: UUID
    model_config = ConfigDict(from_attributes=True)


class UpdateInformantRequest(BaseModel):
    informant_name: Optional[str] = None
    informant_relationship: Optional[RelatioshipType] = None
    informant_contact_no: Optional[str] = None
    informant_signature_path: Optional[str] = None
    declared_date_bs: Optional[date] = None


# ══════════════════════════════════════════════
# Address (स्थायी ठेगाना / मृत्यु स्थान / सूचना दिने व्यक्तिको ठेगाना)
# ══════════════════════════════════════════════

class DeathAddressRequest(BaseModel):
    deceased_province: str
    deceased_district: str
    deceased_municipality: str
    deceased_ward_number: int
    deceased_tole: Optional[str] = None

    death_place_province: str
    death_place_district: str
    death_place_municipality: str
    death_place_ward_number: int
    death_place_tole: Optional[str] = None

    informant_province: Optional[str] = None
    informant_district: Optional[str] = None
    informant_municipality: Optional[str] = None
    informant_ward_number: Optional[int] = None
    informant_tole: Optional[str] = None

    ward_nepali_province: Optional[str] = None
    ward_nepali_district: Optional[str] = None
    ward_nepali_municipality: Optional[str] = None
    ward_nepali_name: Optional[str] = None

    # NOTE: deceased_ward_number / death_place_ward_number are required
    # (plain `int`, not Optional) — an empty string there SHOULD fail
    # validation, since those addresses are mandatory. Only the truly
    # optional informant_ward_number gets the blank->None treatment.
    @field_validator("informant_ward_number", mode="before")
    @classmethod
    def validate_informant_ward_number(cls, value):
        return empty_str_to_none(value)


class UpdateDeathAddressRequest(BaseModel):
    deceased_province: Optional[str] = None
    deceased_district: Optional[str] = None
    deceased_municipality: Optional[str] = None
    deceased_ward_number: Optional[int] = None
    deceased_tole: Optional[str] = None

    death_place_province: Optional[str] = None
    death_place_district: Optional[str] = None
    death_place_municipality: Optional[str] = None
    death_place_ward_number: Optional[int] = None
    death_place_tole: Optional[str] = None

    informant_province: Optional[str] = None
    informant_district: Optional[str] = None
    informant_municipality: Optional[str] = None
    informant_ward_number: Optional[int] = None
    informant_tole: Optional[str] = None

    ward_nepali_province: Optional[str] = None
    ward_nepali_district: Optional[str] = None
    ward_nepali_municipality: Optional[str] = None
    ward_nepali_name: Optional[str] = None

    @field_validator(
        "deceased_ward_number",
        "death_place_ward_number",
        "informant_ward_number",
        mode="before"
    )
    @classmethod
    def validate_ward_number_fields(cls, value):
        return empty_str_to_none(value)


class DeathAddressResponse(BaseModel):
    address_id: UUID

    deceased_province: str
    deceased_district: str
    deceased_municipality: str
    deceased_ward_number: int
    deceased_tole: str | None = None

    death_place_province: str
    death_place_district: str
    death_place_municipality: str
    death_place_ward_number: int
    death_place_tole: str | None = None

    informant_province: str | None = None
    informant_district: str | None = None
    informant_municipality: str | None = None
    informant_ward_number: int | None = None
    informant_tole: str | None = None

    ward_nepali_province: str | None = None
    ward_nepali_district: str | None = None
    ward_nepali_municipality: str | None = None
    ward_nepali_name: str | None = None

    model_config = ConfigDict(from_attributes=True)


# ══════════════════════════════════════════════
# Reject
# ══════════════════════════════════════════════

class DeathRejectRequest(BaseModel):
    reject_text: str


class DeathRejectResponse(DeathRejectRequest):
    reject_id: UUID
    registration_id: UUID
    model_config = ConfigDict(from_attributes=True)


# ══════════════════════════════════════════════
# Documents — citizenship docs have two sides,
# stored/returned separately so both stay legible
# ══════════════════════════════════════════════

class DeathRegistrationDocumentsResponse(BaseModel):
    deceased_citizenship_front_path: Optional[str] = None
    deceased_citizenship_back_path: Optional[str] = None
    informant_citizenship_front_path: Optional[str] = None
    informant_citizenship_back_path: Optional[str] = None
    hospital_death_report_path: Optional[str] = None
    police_report_path: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


# ══════════════════════════════════════════════
# Registration (top level)
# ══════════════════════════════════════════════

class DeathRegistrationRequest(BaseModel):
    register_ward_id: UUID
    registration_no: Optional[str] = None
    page_no: Optional[str] = None
    deceased: DeceasedRequest
    death_detail: DeathDetailRequest
    informant: InformantRequest
    address: DeathAddressRequest


class UpdateDeathRegistrationRequest(BaseModel):
    register_status: Optional[DeathRegistrationStatus] = None
    registration_no: Optional[str] = None
    page_no: Optional[str] = None
    deceased: Optional[UpdateDeceasedRequest] = None
    death_detail: Optional[UpdateDeathDetailRequest] = None
    address: Optional[UpdateDeathAddressRequest] = None
    # Optional: allow clearing/replacing a doc path via this endpoint too
    deceased_citizenship_front_path: Optional[str] = None
    deceased_citizenship_back_path: Optional[str] = None
    informant_citizenship_front_path: Optional[str] = None
    informant_citizenship_back_path: Optional[str] = None
    hospital_death_report_path: Optional[str] = None
    police_report_path: Optional[str] = None


class DeathRegistrationResponse(BaseModel):
    registration_id: UUID
    register_ward_id: UUID
    register_submitted_by: int
    register_status: DeathRegistrationStatus
    registration_no: Optional[str] = None
    page_no: Optional[str] = None

    deceased: Optional[DeceasedResponse] = None
    death_detail: Optional[DeathDetailResponse] = None
    informant: Optional[InformantResponse] = None
    address: Optional[DeathAddressResponse] = None
    reject: Optional[List[DeathRejectResponse]] = []

    # ---- documents ----
    deceased_citizenship_front_path: Optional[str] = None
    deceased_citizenship_back_path: Optional[str] = None
    informant_citizenship_front_path: Optional[str] = None
    informant_citizenship_back_path: Optional[str] = None
    hospital_death_report_path: Optional[str] = None
    police_report_path: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class DeathRegistrationResponseAll(BaseModel):
    registration_id: UUID
    register_ward_id: UUID
    register_submitted_by: int
    register_status: DeathRegistrationStatus

    deceased: Optional[DeceasedResponse] = None
    death_detail: Optional[DeathDetailResponse] = None
    informant: Optional[InformantResponse] = None
    address: Optional[DeathAddressResponse] = None
    reject: List[DeathRejectResponse] = []

    # ---- documents ----
    deceased_citizenship_front_path: Optional[str] = None
    deceased_citizenship_back_path: Optional[str] = None
    informant_citizenship_front_path: Optional[str] = None
    informant_citizenship_back_path: Optional[str] = None
    hospital_death_report_path: Optional[str] = None
    police_report_path: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)