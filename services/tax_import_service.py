"""
Bulk survey-data import for the tax module.

Design (per project discussion):
- Survey team fills a fixed-column Excel template per tax_type.
- DVO uploads it — every row is parsed into `tax_import_row` first.
  Nothing touches the live property_record / business_record /
  rental_unit tables until the DVO explicitly commits the batch.
- Citizen identity is matched by phone_number, which is unique and
  compulsory at registration — so "not found" means "hasn't
  registered yet", not an ambiguous case to guess at.
- Property continuity across years is matched by lalpurja_number
  (a re-survey should update the same property_record, not create
  a duplicate).
"""
import pandas as pd
from datetime import datetime
from sqlalchemy.orm import Session

from model.user_model import UserModel
from model.tax_model import (
    TaxImportBatchModel, TaxImportRowModel, PropertyRecordModel,
    BusinessRecordModel, RentalUnitModel,
)
from services.tax_assessment_service import (
    auto_assess_property, auto_assess_business, auto_assess_rental,
)
from enums.tax_enums import (
    TaxType, ImportBatchStatus, ImportRowMatchStatus, ImportRowAction,
    TaxImportRowStatus, PropertyType, ConstructionType, LocationZone,
)

# Column headers must match exactly — if a sheet doesn't have these,
# reject at parse time with a clear error rather than silently
# misreading columns.
REQUIRED_COLUMNS = {
    TaxType.PROPERTY: [
        "phone_number", "land_area", "property_type",
        "construction_type", "floors", "built_up_area", "location_zone",
        "lalpurja_number", "survey_date",
    ],
    TaxType.BUSINESS: [
        "phone_number", "business_name", "category",
        "scale_tier", "registration_number", "survey_date",
    ],
    TaxType.HOUSE_RENT: [
        "phone_number", "property_lalpurja_number", "unit_type",
        "number_of_rooms", "monthly_rent", "survey_date",
    ],
}


def _read_excel(file_path: str, tax_type: TaxType) -> pd.DataFrame:
    # dtype=str on phone_number avoids pandas silently dropping a
    # leading zero or turning it into a float (e.g. 9812345670.0).
    df = pd.read_excel(file_path, dtype={"phone_number": str})
    df.columns = [str(c).strip() for c in df.columns]

    missing = [c for c in REQUIRED_COLUMNS[tax_type] if c not in df.columns]
    if missing:
        raise ValueError(
            f"Excel file is missing required column(s): {', '.join(missing)}. "
            f"Please use the standard {tax_type.value.lower()} survey template."
        )
    return df


def _row_has_required_data(row: dict, tax_type: TaxType) -> str | None:
    """Returns an error message if a required field is blank/invalid,
    else None."""
    for col in REQUIRED_COLUMNS[tax_type]:
        if pd.isna(row.get(col)) or str(row.get(col)).strip() == "":
            return f"Missing value for '{col}'"
    return None


def import_survey_excel(
    db: Session,
    file_path: str,
    filename: str,
    ward_id,
    tax_type: TaxType,
    uploaded_by_user_id: int,
) -> TaxImportBatchModel:
    df = _read_excel(file_path, tax_type)

    batch = TaxImportBatchModel(
        ward_id=ward_id,
        tax_type=tax_type,
        filename=filename,
        uploaded_by=uploaded_by_user_id,
        status=ImportBatchStatus.PROCESSING,
    )
    db.add(batch)
    db.flush()

    seen_phones_in_batch: dict[str, int] = {}

    for idx, raw_row in df.iterrows():
        row_number = idx + 2  # +1 for 0-index, +1 for header row
        row_dict = raw_row.to_dict()

        error = _row_has_required_data(row_dict, tax_type)
        phone_number = str(row_dict.get("phone_number", "")).strip()

        if error:
            db.add(TaxImportRowModel(
                batch_id=batch.id,
                row_number=row_number,
                raw_data=_json_safe(row_dict),
                phone_number=phone_number or None,
                match_status=ImportRowMatchStatus.INVALID_DATA,
                error_message=error,
                status=TaxImportRowStatus.PENDING,
            ))
            continue

        # duplicate phone WITHIN this batch — since one phone = one user,
        # two rows with the same phone in one file is a survey error,
        # not a valid joint-ownership case (per project decision).
        if phone_number in seen_phones_in_batch:
            db.add(TaxImportRowModel(
                batch_id=batch.id,
                row_number=row_number,
                raw_data=_json_safe(row_dict),
                phone_number=phone_number,
                match_status=ImportRowMatchStatus.DUPLICATE_IN_BATCH,
                error_message=f"Phone number also appears on row {seen_phones_in_batch[phone_number]}",
                status=TaxImportRowStatus.PENDING,
            ))
            continue
        seen_phones_in_batch[phone_number] = row_number

        citizen = db.query(UserModel).filter(
            UserModel.user_phone_number == phone_number
        ).first()

        if not citizen:
            db.add(TaxImportRowModel(
                batch_id=batch.id,
                row_number=row_number,
                raw_data=_json_safe(row_dict),
                phone_number=phone_number,
                match_status=ImportRowMatchStatus.NOT_REGISTERED,
                error_message="No citizen account with this phone number. "
                              "They must register on the website before this row can be committed.",
                status=TaxImportRowStatus.PENDING,
            ))
            continue

        # A citizen's phone number can only be entered against the ward
        # they're actually registered under — otherwise a DVO in one ward
        # could (by mistake or otherwise) attach tax data to someone
        # registered in a different ward. str() comparison since ward_id
        # is a UUID column on both sides.
        if str(citizen.ward_id) != str(ward_id):
            db.add(TaxImportRowModel(
                batch_id=batch.id,
                row_number=row_number,
                raw_data=_json_safe(row_dict),
                phone_number=phone_number,
                matched_citizen_id=citizen.user_id,
                match_status=ImportRowMatchStatus.WARD_MISMATCH,
                error_message="This phone number is registered under a different ward. "
                              "Tax data can only be entered for citizens of this ward.",
                status=TaxImportRowStatus.PENDING,
            ))
            continue

        # property continuity check — only meaningful for PROPERTY rows
        matched_property_id = None
        import_action = None
        if tax_type == TaxType.PROPERTY:
            lalpurja = str(row_dict.get("lalpurja_number", "")).strip()
            existing = None
            if lalpurja and lalpurja.lower() != "nan":
                existing = db.query(PropertyRecordModel).filter(
                    PropertyRecordModel.lalpurja_number == lalpurja
                ).first()
            if existing:
                matched_property_id = existing.id
                import_action = ImportRowAction.UPDATE
            elif lalpurja and lalpurja.lower() != "nan":
                import_action = ImportRowAction.NEW
            else:
                import_action = ImportRowAction.NEEDS_REVIEW  # no lalpurja — needs manual confirmation

        db.add(TaxImportRowModel(
            batch_id=batch.id,
            row_number=row_number,
            raw_data=_json_safe(row_dict),
            phone_number=phone_number,
            matched_citizen_id=citizen.user_id,
            matched_property_id=matched_property_id,
            match_status=ImportRowMatchStatus.MATCHED,
            import_action=import_action,
            status=TaxImportRowStatus.PENDING,
        ))

    batch.status = ImportBatchStatus.REVIEW
    db.commit()
    db.refresh(batch)
    return batch


def _json_safe(row_dict: dict) -> dict:
    """pandas/NumPy types (Timestamp, int64, nan) aren't JSON-serializable
    as-is — normalize before storing in the JSON column."""
    out = {}
    for k, v in row_dict.items():
        if pd.isna(v):
            out[k] = None
        elif isinstance(v, (pd.Timestamp, datetime)):
            out[k] = v.isoformat()
        else:
            out[k] = v.item() if hasattr(v, "item") else v
    return out


def commit_batch(db: Session, batch: TaxImportBatchModel, committed_by_user_id: int):
    """Pushes every APPROVED/EDITED row into the live tables in one
    transaction. Rows left PENDING or REJECTED are skipped and remain
    in tax_import_row for audit — they are not deleted.

    After the batch itself commits, each affected record is run through
    the matching auto_assess_* helper, which calculates and stores the
    tax bill using the ward's most recently set rate. If the Ward
    Secretary hasn't set a rate yet, auto_assess_* is a no-op for that
    record — it stays uncalculated until a rate exists, rather than
    blocking the import."""
    property_records_to_assess = []
    business_records_to_assess = []
    rental_units_to_assess = []

    try:
        for row in [r for r in batch.rows if r.status in (TaxImportRowStatus.APPROVED, TaxImportRowStatus.EDITED)]:
            data = row.raw_data
            if batch.tax_type == TaxType.PROPERTY:
                if row.matched_property_id:
                    record = db.query(PropertyRecordModel).get(row.matched_property_id)
                    record.land_area_sqm = data.get("land_area")
                    record.built_up_area_sqm = data.get("built_up_area")
                    record.property_type = data.get("property_type")
                    record.construction_type = data.get("construction_type")
                    record.number_of_floors = data.get("floors")
                    record.location_zone = data.get("location_zone")
                    record.entered_by = committed_by_user_id
                    record.import_batch_id = batch.id
                else:
                    record = PropertyRecordModel(
                        citizen_id=row.matched_citizen_id,
                        ward_id=batch.ward_id,
                        lalpurja_number=data.get("lalpurja_number"),
                        land_area_sqm=data.get("land_area"),
                        built_up_area_sqm=data.get("built_up_area"),
                        property_type=data.get("property_type"),
                        construction_type=data.get("construction_type"),
                        number_of_floors=data.get("floors"),
                        location_zone=data.get("location_zone"),
                        entered_by=committed_by_user_id,
                        import_batch_id=batch.id,
                    )
                    db.add(record)
                db.flush()  # assigns record.id so it can be assessed below
                property_records_to_assess.append(record)

            elif batch.tax_type == TaxType.BUSINESS:
                record = BusinessRecordModel(
                    citizen_id=row.matched_citizen_id,
                    ward_id=batch.ward_id,
                    business_name=data.get("business_name"),
                    category_id=data.get("category"),  # expects category UUID resolved beforehand
                    scale_tier=data.get("scale_tier"),
                    registration_number=data.get("registration_number"),
                    entered_by=committed_by_user_id,
                    import_batch_id=batch.id,
                )
                db.add(record)
                db.flush()
                business_records_to_assess.append(record)

            elif batch.tax_type == TaxType.HOUSE_RENT:
                property_record = db.query(PropertyRecordModel).filter(
                    PropertyRecordModel.lalpurja_number == data.get("property_lalpurja_number")
                ).first()
                if not property_record:
                    row.status = TaxImportRowStatus.REJECTED
                    row.error_message = "No property found for this lalpurja number — commit the property survey first."
                    continue
                rental_unit = RentalUnitModel(
                    property_id=property_record.id,
                    unit_type=data.get("unit_type"),
                    number_of_rooms=data.get("number_of_rooms"),
                    monthly_rent=data.get("monthly_rent"),
                    entered_by=committed_by_user_id,
                )
                db.add(rental_unit)
                db.flush()
                rental_units_to_assess.append(rental_unit)

        batch.status = ImportBatchStatus.COMMITTED
        batch.committed_at = datetime.utcnow()
        db.commit()
    except Exception:
        db.rollback()
        raise

    # Auto-calculate tax for everything just committed. Each helper
    # commits its own assessment independently — a rate missing for one
    # record doesn't block the others.
    for record in property_records_to_assess:
        db.refresh(record)
        auto_assess_property(db, record)
    for record in business_records_to_assess:
        db.refresh(record)
        auto_assess_business(db, record)
    for rental_unit in rental_units_to_assess:
        db.refresh(rental_unit)
        auto_assess_rental(db, rental_unit)