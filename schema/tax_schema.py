from pydantic import BaseModel, ConfigDict
from typing import Optional, List, Any
from uuid import UUID
from datetime import datetime
from enums.tax_enums import (
    TaxType, PropertyType, ConstructionType, LocationZone, BusinessScaleTier,
    RentalUnitType, TaxRecordStatus, ImportBatchStatus, ImportRowMatchStatus,
    ImportRowAction, TaxImportRowStatus, TaxAssessmentStatus, TaxPaymentMethod,
    TaxDisputeStatus,
)


# ══════════════════════ DIRECT ENTRY (DVO adds one record at a time) ══════════════════════
class PropertyRecordCreateRequest(BaseModel):
    phone_number: str
    lalpurja_number: Optional[str] = None
    land_area_sqm: float
    built_up_area_sqm: Optional[float] = None
    property_type: PropertyType
    construction_type: Optional[ConstructionType] = None
    location_zone: LocationZone
    number_of_floors: Optional[int] = None


class PropertyRecordUpdateRequest(BaseModel):
    lalpurja_number: Optional[str] = None
    land_area_sqm: Optional[float] = None
    built_up_area_sqm: Optional[float] = None
    property_type: Optional[PropertyType] = None
    construction_type: Optional[ConstructionType] = None
    location_zone: Optional[LocationZone] = None
    number_of_floors: Optional[int] = None


class BusinessCategoryResponse(BaseModel):
    id: UUID
    name: str
    base_fee: float
    model_config = ConfigDict(from_attributes=True)


class BusinessRecordCreateRequest(BaseModel):
    phone_number: str
    business_name: str
    category_id: UUID
    scale_tier: BusinessScaleTier
    registration_number: Optional[str] = None


class BusinessRecordUpdateRequest(BaseModel):
    business_name: Optional[str] = None
    category_id: Optional[UUID] = None
    scale_tier: Optional[BusinessScaleTier] = None
    registration_number: Optional[str] = None


# ══════════════════════ WARD TAX RATE ══════════════════════
class WardTaxRateRequest(BaseModel):
    tax_type: TaxType
    property_type: Optional[PropertyType] = None
    construction_type: Optional[ConstructionType] = None
    location_zone: Optional[LocationZone] = None
    business_scale_tier: Optional[BusinessScaleTier] = None
    rate_value: float
    fiscal_year: str


class WardTaxRateResponse(WardTaxRateRequest):
    id: UUID
    ward_id: UUID
    effective_from: datetime
    updated_by: Optional[int] = None
    model_config = ConfigDict(from_attributes=True)


# ══════════════════════ PROPERTY / BUSINESS / RENTAL ══════════════════════
class PropertyRecordResponse(BaseModel):
    id: UUID
    citizen_id: Optional[int] = None
    ward_id: UUID
    lalpurja_number: Optional[str] = None
    land_area_sqm: float
    built_up_area_sqm: Optional[float] = None
    property_type: PropertyType
    construction_type: Optional[ConstructionType] = None
    location_zone: LocationZone
    number_of_floors: Optional[int] = None
    status: TaxRecordStatus
    survey_date: datetime
    model_config = ConfigDict(from_attributes=True)


class BusinessRecordResponse(BaseModel):
    id: UUID
    citizen_id: Optional[int] = None
    ward_id: UUID
    business_name: str
    category_id: UUID
    scale_tier: BusinessScaleTier
    registration_number: Optional[str] = None
    status: TaxRecordStatus
    survey_date: datetime
    model_config = ConfigDict(from_attributes=True)


class RentalUnitResponse(BaseModel):
    id: UUID
    property_id: UUID
    unit_type: RentalUnitType
    number_of_rooms: Optional[int] = None
    monthly_rent: float
    is_active: bool
    model_config = ConfigDict(from_attributes=True)


class TaxDisputeRequest(BaseModel):
    reason: str


class TaxDisputeResponse(TaxDisputeRequest):
    id: UUID
    assessment_id: UUID
    citizen_id: int
    status: TaxDisputeStatus
    resolution_note: Optional[str] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class TaxDisputeResolveRequest(BaseModel):
    status: TaxDisputeStatus
    resolution_note: Optional[str] = None


# ══════════════════════ ASSESSMENT / PAYMENT ══════════════════════
class TaxAssessmentResponse(BaseModel):
    id: UUID
    record_id: UUID
    tax_type: TaxType
    citizen_id: int
    citizen_name: Optional[str] = None
    ward_id: UUID
    fiscal_year: str
    base_amount: float
    penalty_amount: float
    discount_amount: float
    total_due: float
    due_date: datetime
    status: TaxAssessmentStatus
    model_config = ConfigDict(from_attributes=True)


class TaxPaymentRequest(BaseModel):
    assessment_id: UUID
    amount_paid: float
    method: TaxPaymentMethod


class TaxPaymentResponse(BaseModel):
    id: UUID
    assessment_id: UUID
    amount_paid: float
    method: TaxPaymentMethod
    receipt_no: str
    paid_at: datetime
    gateway_status: Optional[str] = None
    transaction_id: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


class KhaltiInitiateRequest(BaseModel):
    assessment_id: UUID


class KhaltiInitiateResponse(BaseModel):
    payment_url: str
    pidx: str


# ══════════════════════ EXCEL IMPORT ══════════════════════
class TaxImportRowResponse(BaseModel):
    id: UUID
    row_number: int
    raw_data: dict
    phone_number: Optional[str] = None
    matched_citizen_id: Optional[int] = None
    matched_citizen_name: Optional[str] = None
    matched_property_id: Optional[UUID] = None
    match_status: ImportRowMatchStatus
    import_action: Optional[ImportRowAction] = None
    error_message: Optional[str] = None
    status: TaxImportRowStatus
    model_config = ConfigDict(from_attributes=True)


class TaxImportBatchResponse(BaseModel):
    id: UUID
    ward_id: UUID
    tax_type: TaxType
    filename: str
    status: ImportBatchStatus
    uploaded_at: datetime
    rows: List[TaxImportRowResponse] = []
    model_config = ConfigDict(from_attributes=True)


class TaxImportRowEditRequest(BaseModel):
    """DVO correction to one staged row before commit — only the fields
    that need fixing (e.g. mis-typed phone number) need to be sent."""
    raw_data: Optional[dict] = None
    phone_number: Optional[str] = None
    status: Optional[TaxImportRowStatus] = None  # e.g. approve / reject this row