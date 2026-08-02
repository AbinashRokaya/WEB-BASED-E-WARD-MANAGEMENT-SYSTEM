# schema/recommendation_schema.py
from pydantic import BaseModel, ConfigDict, field_validator
from typing import Optional
from uuid import UUID
import re

from enums.recommendation_enum import RecommendationLetterType, RecommendationStatus

NEPALI_REGEX = re.compile(r'^[\u0900-\u097F\s।.,()-]+$')


class RecommendationAddressSchema(BaseModel):
    """
    Mirrors the shape of BirthRegistration's `address` payload:
    the raw (English) selection made against the ward list, plus the
    Nepali labels that come along with the selected ward, snapshotted
    at submission time so the printed letter doesn't depend on the
    ward table staying unchanged later.
    """
    applicant_province: str
    applicant_district: str
    applicant_municipality: str
    applicant_ward_number: int
    applicant_tole: Optional[str] = None

    ward_nepali_province: Optional[str] = None
    ward_nepali_district: Optional[str] = None
    ward_nepali_municipality: Optional[str] = None
    ward_nepali_name: Optional[str] = None
    ward_type: Optional[str] = None


class RecommendationLetterRequest(BaseModel):
    letter_type: RecommendationLetterType
    letter_type_other: Optional[str] = None

    applicant_full_name_np: str
    applicant_full_name_en: str
    applicant_citizenship_no: str
    applicant_contact_no: Optional[str] = None

    # FK to the ward table — the ward selected via the cascading
    # province/district/municipality/ward dropdown on the frontend,
    # same as BirthRegistration's `register_ward_id`.
    register_ward_id: UUID
    address: RecommendationAddressSchema

    purpose: str

    @field_validator("applicant_full_name_np", mode="before")
    @classmethod
    def validate_np_name(cls, value):
        if value is None:
            return value
        value = value.strip()
        if value and not NEPALI_REGEX.fullmatch(value):
            raise ValueError("Name must contain only Nepali (Devanagari) characters.")
        return value

    @field_validator("letter_type_other")
    @classmethod
    def validate_other_reason(cls, value, info):
        # if letter_type is OTHER, letter_type_other should be provided
        if info.data.get("letter_type") == RecommendationLetterType.OTHER and not value:
            raise ValueError("Please specify the letter type when selecting OTHER.")
        return value


class RejectRequest(BaseModel):
    reject_text: str


class RejectResponse(RejectRequest):
    reject_id: UUID
    letter_id: UUID
    model_config = ConfigDict(from_attributes=True)


class RecommendationLetterResponse(BaseModel):
    letter_id: UUID
    register_ward_id: UUID
    register_submitted_by: int
    register_status: RecommendationStatus

    letter_type: RecommendationLetterType
    letter_type_other: Optional[str] = None

    applicant_full_name_np: str
    applicant_full_name_en: str
    applicant_citizenship_no: str
    applicant_contact_no: Optional[str] = None

    applicant_province: str
    applicant_district: str
    applicant_municipality: str
    applicant_ward_number: int
    applicant_tole: Optional[str] = None

    ward_nepali_province: Optional[str] = None
    ward_nepali_district: Optional[str] = None
    ward_nepali_municipality: Optional[str] = None
    ward_nepali_name: Optional[str] = None
    ward_type: Optional[str] = None

    purpose: str

    applicant_citizenship_front_path: Optional[str] = None
    applicant_citizenship_back_path: Optional[str] = None
    supporting_document_path: Optional[str] = None

    # exposed so EditRecommendationModal.jsx's formData.reject?.[0]?.reject_text
    # can show the previous rejection reason when a REJECTED letter is
    # reopened for review — mirrors the `reject` relationship on the model.
    reject: list[RejectResponse] = []

    model_config = ConfigDict(from_attributes=True)


class UpdateRecommendationRequest(BaseModel):
    register_status: Optional[RecommendationStatus] = None
    purpose: Optional[str] = None
    applicant_contact_no: Optional[str] = None