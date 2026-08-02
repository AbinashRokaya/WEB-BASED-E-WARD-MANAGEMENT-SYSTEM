"""
Turns a committed property/business/rental record + the active
ward_tax_rate into a tax_assessment, and computes overdue penalties.
"""
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session

from model.tax_model import (
    WardTaxRateModel, TaxAssessmentModel, PropertyRecordModel,
    BusinessRecordModel, RentalUnitModel,
)
from enums.tax_enums import TaxType, TaxAssessmentStatus

LATE_PENALTY_ANNUAL_RATE = Decimal("0.15")   # 15%/year, matches real ward practice
EARLY_PAYMENT_DISCOUNT = Decimal("0.10")     # optional — 10% if paid before due_date


def _active_rate(db: Session, ward_id, tax_type: TaxType, fiscal_year: str, **filters):
    query = db.query(WardTaxRateModel).filter(
        WardTaxRateModel.ward_id == ward_id,
        WardTaxRateModel.tax_type == tax_type,
        WardTaxRateModel.fiscal_year == fiscal_year,
    )
    for field, value in filters.items():
        if value is not None:
            query = query.filter(getattr(WardTaxRateModel, field) == value)
    # most recently effective rate wins if more than one matches
    return query.order_by(WardTaxRateModel.effective_from.desc()).first()


def generate_property_assessment(db: Session, property_record: PropertyRecordModel, fiscal_year: str, due_date: datetime):
    rate = _active_rate(
        db, property_record.ward_id, TaxType.PROPERTY, fiscal_year,
        property_type=property_record.property_type,
        construction_type=property_record.construction_type,
        location_zone=property_record.location_zone,
    )
    if not rate:
        raise ValueError(
            f"No tax rate configured for this ward/property type/zone in FY {fiscal_year}. "
            "Ask the Ward Secretary to set one first."
        )

    base_amount = Decimal(str(property_record.land_area_sqm)) * Decimal(str(rate.rate_value))
    if property_record.built_up_area_sqm:
        base_amount += Decimal(str(property_record.built_up_area_sqm)) * Decimal(str(rate.rate_value))

    return _upsert_assessment(
        db, record_id=property_record.id, tax_type=TaxType.PROPERTY,
        citizen_id=property_record.citizen_id, ward_id=property_record.ward_id,
        fiscal_year=fiscal_year, base_amount=base_amount, due_date=due_date,
    )


def generate_rental_assessment(db: Session, rental_unit: RentalUnitModel, fiscal_year: str, due_date: datetime):
    property_record = rental_unit.property
    rate = _active_rate(db, property_record.ward_id, TaxType.HOUSE_RENT, fiscal_year)
    if not rate:
        raise ValueError(f"No house-rent tax rate configured for this ward in FY {fiscal_year}.")

    annual_rent = Decimal(str(rental_unit.monthly_rent)) * 12
    base_amount = annual_rent * (Decimal(str(rate.rate_value)) / 100)

    return _upsert_assessment(
        db, record_id=rental_unit.id, tax_type=TaxType.HOUSE_RENT,
        citizen_id=property_record.citizen_id, ward_id=property_record.ward_id,
        fiscal_year=fiscal_year, base_amount=base_amount, due_date=due_date,
    )


def generate_business_assessment(db: Session, business_record: BusinessRecordModel, fiscal_year: str, due_date: datetime):
    rate = _active_rate(
        db, business_record.ward_id, TaxType.BUSINESS, fiscal_year,
        business_scale_tier=business_record.scale_tier,
    )
    base_fee = business_record.category.base_fee if business_record.category else Decimal("0")
    rate_multiplier = (Decimal(str(rate.rate_value)) / 100) if rate else Decimal("0")
    base_amount = Decimal(str(base_fee)) * (1 + rate_multiplier)

    return _upsert_assessment(
        db, record_id=business_record.id, tax_type=TaxType.BUSINESS,
        citizen_id=business_record.citizen_id, ward_id=business_record.ward_id,
        fiscal_year=fiscal_year, base_amount=base_amount, due_date=due_date,
    )


def _upsert_assessment(db, record_id, tax_type, citizen_id, ward_id, fiscal_year, base_amount, due_date):
    existing = db.query(TaxAssessmentModel).filter(
        TaxAssessmentModel.record_id == record_id,
        TaxAssessmentModel.tax_type == tax_type,
        TaxAssessmentModel.fiscal_year == fiscal_year,
    ).first()

    if existing:
        # forward-only: re-generating updates an unpaid assessment,
        # never rewrites one that's already paid
        if existing.status == TaxAssessmentStatus.PAID:
            return existing
        existing.base_amount = base_amount
        existing.total_due = base_amount + existing.penalty_amount - existing.discount_amount
        db.commit()
        db.refresh(existing)
        return existing

    assessment = TaxAssessmentModel(
        id=uuid.uuid4(),
        record_id=record_id,
        tax_type=tax_type,
        citizen_id=citizen_id,
        ward_id=ward_id,
        fiscal_year=fiscal_year,
        base_amount=base_amount,
        penalty_amount=0,
        discount_amount=0,
        total_due=base_amount,
        due_date=due_date,
        status=TaxAssessmentStatus.ASSESSED,
    )
    db.add(assessment)
    db.commit()
    db.refresh(assessment)
    return assessment


def _latest_fiscal_year_for_ward(db: Session, ward_id, tax_type: TaxType) -> str | None:
    """The Ward Secretary sets a rate with a fiscal_year every time they
    add/update one — so 'the fiscal year currently being taxed' is simply
    whichever rate was set most recently for this ward+tax_type. Avoids
    doing BS/AD calendar math entirely; if the Secretary hasn't set a
    rate yet, there's nothing to calculate against, and callers should
    treat None as 'not ready yet', not an error."""
    rate = db.query(WardTaxRateModel).filter(
        WardTaxRateModel.ward_id == ward_id,
        WardTaxRateModel.tax_type == tax_type,
    ).order_by(WardTaxRateModel.effective_from.desc()).first()
    return rate.fiscal_year if rate else None


DEFAULT_DUE_IN_DAYS = 90


def auto_assess_property(db: Session, property_record: PropertyRecordModel):
    """Called right after a property record is created/updated (both the
    single-entry endpoint and the Excel commit path) — automatically
    calculates and stores the tax bill using whatever rate the Ward
    Secretary has most recently set for this ward. Returns None (not an
    error) if the Secretary hasn't configured a rate yet — the record is
    still saved either way; the assessment just waits until a rate exists."""
    fiscal_year = _latest_fiscal_year_for_ward(db, property_record.ward_id, TaxType.PROPERTY)
    if not fiscal_year:
        return None
    due_date = datetime.utcnow() + timedelta(days=DEFAULT_DUE_IN_DAYS)
    try:
        return generate_property_assessment(db, property_record, fiscal_year, due_date)
    except ValueError:
        # rate exists for a DIFFERENT property_type/construction/zone
        # combination than this specific property — still not ready
        return None


def auto_assess_business(db: Session, business_record: BusinessRecordModel):
    fiscal_year = _latest_fiscal_year_for_ward(db, business_record.ward_id, TaxType.BUSINESS)
    if not fiscal_year:
        return None
    due_date = datetime.utcnow() + timedelta(days=DEFAULT_DUE_IN_DAYS)
    try:
        return generate_business_assessment(db, business_record, fiscal_year, due_date)
    except ValueError:
        return None


def auto_assess_rental(db: Session, rental_unit: RentalUnitModel):
    fiscal_year = _latest_fiscal_year_for_ward(db, rental_unit.property.ward_id, TaxType.HOUSE_RENT)
    if not fiscal_year:
        return None
    due_date = datetime.utcnow() + timedelta(days=DEFAULT_DUE_IN_DAYS)
    try:
        return generate_rental_assessment(db, rental_unit, fiscal_year, due_date)
    except ValueError:
        return None


def apply_overdue_penalty(db: Session, assessment: TaxAssessmentModel) -> TaxAssessmentModel:
    """Call this on read (or via a scheduled job) — if unpaid past
    due_date, add 15%/year pro-rated penalty."""
    if assessment.status == TaxAssessmentStatus.PAID:
        return assessment

    now = datetime.utcnow()
    if now <= assessment.due_date:
        return assessment

    days_overdue = (now - assessment.due_date).days
    penalty = Decimal(str(assessment.base_amount)) * LATE_PENALTY_ANNUAL_RATE * (Decimal(days_overdue) / 365)
    assessment.penalty_amount = penalty
    assessment.total_due = Decimal(str(assessment.base_amount)) + penalty - Decimal(str(assessment.discount_amount))
    assessment.status = TaxAssessmentStatus.OVERDUE
    db.commit()
    db.refresh(assessment)
    return assessment