import os
import shutil
import logging
import uuid as uuid_lib
from datetime import datetime, timedelta
from uuid import UUID
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from fastapi.responses import JSONResponse, RedirectResponse
from starlette.concurrency import run_in_threadpool

from database.db import get_db
from model.tax_model import (
    WardTaxRateModel, PropertyRecordModel, BusinessRecordModel, RentalUnitModel,
    TaxImportBatchModel, TaxImportRowModel, TaxAssessmentModel, TaxPaymentModel,
    TaxDisputeModel, BusinessCategoryModel,
)
from enums.tax_enums import (
    TaxType, TaxImportRowStatus, TaxAssessmentStatus, TaxDisputeStatus,
    ImportBatchStatus, ImportRowMatchStatus, TaxPaymentMethod,
)
from schema.tax_schema import (
    WardTaxRateRequest, WardTaxRateResponse, PropertyRecordResponse,
    BusinessRecordResponse, RentalUnitResponse, TaxAssessmentResponse,
    TaxPaymentRequest, TaxPaymentResponse, TaxImportBatchResponse,
    TaxImportRowResponse, TaxImportRowEditRequest, TaxDisputeRequest,
    TaxDisputeResponse, TaxDisputeResolveRequest,
    PropertyRecordCreateRequest, PropertyRecordUpdateRequest,
    BusinessRecordCreateRequest, BusinessRecordUpdateRequest,
    BusinessCategoryResponse, KhaltiInitiateRequest, KhaltiInitiateResponse,
)
from services.khalti_service import (
    initiate_khalti_payment, lookup_khalti_payment, FRONTEND_BASE_URL,
)
from services.tax_import_service import import_survey_excel, commit_batch
from services.tax_assessment_service import (
    generate_property_assessment, generate_rental_assessment,
    generate_business_assessment, apply_overdue_penalty,
    auto_assess_property, auto_assess_business, auto_assess_rental,
)
from services.tax_receipt_service import issue_tax_receipt
from auth.current_user import require_permission

router = APIRouter(prefix="/v1/tax", tags=["tax"])
logger = logging.getLogger(__name__)


def serialize(obj, schema):
    return schema.from_orm(obj).model_dump(mode="json")


# ══════════════════════════════════════════════════════════════
# WARD SECRETARY — rate configuration, scoped to their own ward.
# ══════════════════════════════════════════════════════════════
def _assert_ward_scope(current_user, ward_id: UUID):
    is_admin = str(getattr(current_user, "user_role", "")).upper().endswith("ADMIN")
    if is_admin:
        return
    if str(current_user.user_ward_id) != str(ward_id):
        raise HTTPException(status_code=403, detail="You can only manage tax rates for your own ward")


def _match_citizen_for_own_ward(db, current_user, phone_number: str):
    from model.user_model import UserModel
    citizen = db.query(UserModel).filter(UserModel.user_phone_number == phone_number).first()
    if not citizen:
        raise HTTPException(
            status_code=400,
            detail="No citizen account with this phone number. They must register on the website first.",
        )
    if str(citizen.ward_id) != str(current_user.user_ward_id):
        raise HTTPException(
            status_code=400,
            detail="This phone number is registered under a different ward. "
                   "You can only enter tax data for citizens of your own ward.",
        )
    return citizen


@router.get("/rates/mine")
def get_my_ward_tax_rates(
    fiscal_year: Optional[str] = None,
    db=Depends(get_db),
    current_user=Depends(require_permission("read_user")),
):
    query = db.query(WardTaxRateModel).filter(
        WardTaxRateModel.ward_id == current_user.user_ward_id
    )
    if fiscal_year:
        query = query.filter(WardTaxRateModel.fiscal_year == fiscal_year)
    rates = query.order_by(WardTaxRateModel.effective_from.desc()).all()

    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "status_code": 200,
            "message": "Tax rates fetched successfully",
            "total": len(rates),
            "data": [serialize(r, WardTaxRateResponse) for r in rates],
        },
    )


@router.post("/rates/mine")
def create_my_ward_tax_rate(
    request: WardTaxRateRequest,
    db=Depends(get_db),
    current_user=Depends(require_permission("update_user")),
):
    rate = WardTaxRateModel(
        ward_id=current_user.user_ward_id,
        updated_by=current_user.user_id,
        **request.model_dump(),
    )
    db.add(rate)
    db.commit()
    db.refresh(rate)

    return JSONResponse(
        status_code=201,
        content={
            "success": True,
            "status_code": 201,
            "message": "Tax rate created — applies to new assessments only; already-issued bills are unaffected",
            "data": serialize(rate, WardTaxRateResponse),
        },
    )


@router.put("/rates/mine/{rate_id}")
def update_my_ward_tax_rate(
    rate_id: UUID,
    request: WardTaxRateRequest,
    db=Depends(get_db),
    current_user=Depends(require_permission("update_user")),
):
    rate = db.query(WardTaxRateModel).filter(
        WardTaxRateModel.id == rate_id,
        WardTaxRateModel.ward_id == current_user.user_ward_id,
    ).first()
    if not rate:
        raise HTTPException(status_code=404, detail="Tax rate not found in your ward")

    for field, value in request.model_dump().items():
        setattr(rate, field, value)
    rate.updated_by = current_user.user_id
    db.commit()
    db.refresh(rate)

    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "status_code": 200,
            "message": "Tax rate updated — applies to new assessments only",
            "data": serialize(rate, WardTaxRateResponse),
        },
    )


@router.post("/assessments/recalculate")
def recalculate_ward_assessments(
    db=Depends(get_db),
    current_user=Depends(require_permission("update_user")),
):
    ward_id = current_user.user_ward_id

    assessed_count = 0

    properties = db.query(PropertyRecordModel).filter(PropertyRecordModel.ward_id == ward_id).all()
    for record in properties:
        if auto_assess_property(db, record):
            assessed_count += 1

    businesses = db.query(BusinessRecordModel).filter(BusinessRecordModel.ward_id == ward_id).all()
    for record in businesses:
        if auto_assess_business(db, record):
            assessed_count += 1

    rentals = (
        db.query(RentalUnitModel)
        .join(PropertyRecordModel, RentalUnitModel.property_id == PropertyRecordModel.id)
        .filter(PropertyRecordModel.ward_id == ward_id)
        .all()
    )
    for rental_unit in rentals:
        if auto_assess_rental(db, rental_unit):
            assessed_count += 1

    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "status_code": 200,
            "message": f"Recalculated {assessed_count} assessment(s) using current rates.",
            "data": {"assessed_count": assessed_count},
        },
    )


@router.get("/wards/{ward_id}/rates")
def get_ward_tax_rates(
    ward_id: UUID,
    fiscal_year: Optional[str] = None,
    db=Depends(get_db),
    current_user=Depends(require_permission("read_user")),
):
    query = db.query(WardTaxRateModel).filter(WardTaxRateModel.ward_id == ward_id)
    if fiscal_year:
        query = query.filter(WardTaxRateModel.fiscal_year == fiscal_year)
    rates = query.order_by(WardTaxRateModel.effective_from.desc()).all()

    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "status_code": 200,
            "message": "Tax rates fetched successfully",
            "total": len(rates),
            "data": [serialize(r, WardTaxRateResponse) for r in rates],
        },
    )


@router.post("/wards/{ward_id}/rates")
def create_ward_tax_rate(
    ward_id: UUID,
    request: WardTaxRateRequest,
    db=Depends(get_db),
    current_user=Depends(require_permission("update_user")),
):
    _assert_ward_scope(current_user, ward_id)

    rate = WardTaxRateModel(
        ward_id=ward_id,
        updated_by=current_user.user_id,
        **request.model_dump(),
    )
    db.add(rate)
    db.commit()
    db.refresh(rate)

    return JSONResponse(
        status_code=201,
        content={
            "success": True,
            "status_code": 201,
            "message": "Tax rate created — applies to new assessments only; already-issued bills are unaffected",
            "data": serialize(rate, WardTaxRateResponse),
        },
    )


@router.put("/wards/{ward_id}/rates/{rate_id}")
def update_ward_tax_rate(
    ward_id: UUID,
    rate_id: UUID,
    request: WardTaxRateRequest,
    db=Depends(get_db),
    current_user=Depends(require_permission("update_user")),
):
    _assert_ward_scope(current_user, ward_id)

    rate = db.query(WardTaxRateModel).filter(
        WardTaxRateModel.id == rate_id, WardTaxRateModel.ward_id == ward_id
    ).first()
    if not rate:
        raise HTTPException(status_code=404, detail="Tax rate not found")

    for field, value in request.model_dump().items():
        setattr(rate, field, value)
    rate.updated_by = current_user.user_id
    db.commit()
    db.refresh(rate)

    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "status_code": 200,
            "message": "Tax rate updated — applies to new assessments only",
            "data": serialize(rate, WardTaxRateResponse),
        },
    )


# ══════════════════════════════════════════════════════════════
# PROPERTY / BUSINESS RECORDS — direct single-entry by DVO
# ══════════════════════════════════════════════════════════════
@router.get("/properties")
def list_property_records(
    db=Depends(get_db),
    current_user=Depends(require_permission("read_user")),
):
    records = db.query(PropertyRecordModel).filter(
        PropertyRecordModel.ward_id == current_user.user_ward_id
    ).order_by(PropertyRecordModel.created_at.desc()).all()

    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "status_code": 200,
            "message": "Property records fetched successfully",
            "total": len(records),
            "data": [serialize(r, PropertyRecordResponse) for r in records],
        },
    )


@router.post("/properties")
def create_property_record(
    request: PropertyRecordCreateRequest,
    db=Depends(get_db),
    current_user=Depends(require_permission("validate_data")),
):
    citizen = _match_citizen_for_own_ward(db, current_user, request.phone_number)

    record = PropertyRecordModel(
        citizen_id=citizen.user_id,
        ward_id=current_user.user_ward_id,
        entered_by=current_user.user_id,
        **request.model_dump(exclude={"phone_number"}),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    auto_assess_property(db, record)

    return JSONResponse(
        status_code=201,
        content={
            "success": True,
            "status_code": 201,
            "message": "Property record created",
            "data": serialize(record, PropertyRecordResponse),
        },
    )


@router.put("/properties/{property_id}")
def update_property_record(
    property_id: UUID,
    request: PropertyRecordUpdateRequest,
    db=Depends(get_db),
    current_user=Depends(require_permission("validate_data")),
):
    record = db.query(PropertyRecordModel).filter(PropertyRecordModel.id == property_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Property record not found")
    if str(record.ward_id) != str(current_user.user_ward_id):
        raise HTTPException(status_code=403, detail="You can only edit records in your own ward")

    for field, value in request.model_dump(exclude_unset=True).items():
        setattr(record, field, value)
    record.entered_by = current_user.user_id
    db.commit()
    db.refresh(record)
    auto_assess_property(db, record)

    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "status_code": 200,
            "message": "Property record updated",
            "data": serialize(record, PropertyRecordResponse),
        },
    )


@router.get("/business-categories")
def list_business_categories(
    db=Depends(get_db),
    current_user=Depends(require_permission("read_user")),
):
    categories = db.query(BusinessCategoryModel).order_by(BusinessCategoryModel.name).all()
    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "status_code": 200,
            "message": "Business categories fetched successfully",
            "data": [serialize(c, BusinessCategoryResponse) for c in categories],
        },
    )


@router.get("/businesses")
def list_business_records(
    db=Depends(get_db),
    current_user=Depends(require_permission("read_user")),
):
    records = db.query(BusinessRecordModel).filter(
        BusinessRecordModel.ward_id == current_user.user_ward_id
    ).order_by(BusinessRecordModel.created_at.desc()).all()

    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "status_code": 200,
            "message": "Business records fetched successfully",
            "total": len(records),
            "data": [serialize(r, BusinessRecordResponse) for r in records],
        },
    )


@router.post("/businesses")
def create_business_record(
    request: BusinessRecordCreateRequest,
    db=Depends(get_db),
    current_user=Depends(require_permission("validate_data")),
):
    citizen = _match_citizen_for_own_ward(db, current_user, request.phone_number)

    record = BusinessRecordModel(
        citizen_id=citizen.user_id,
        ward_id=current_user.user_ward_id,
        entered_by=current_user.user_id,
        **request.model_dump(exclude={"phone_number"}),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    auto_assess_business(db, record)

    return JSONResponse(
        status_code=201,
        content={
            "success": True,
            "status_code": 201,
            "message": "Business record created",
            "data": serialize(record, BusinessRecordResponse),
        },
    )


@router.put("/businesses/{business_id}")
def update_business_record(
    business_id: UUID,
    request: BusinessRecordUpdateRequest,
    db=Depends(get_db),
    current_user=Depends(require_permission("validate_data")),
):
    record = db.query(BusinessRecordModel).filter(BusinessRecordModel.id == business_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Business record not found")
    if str(record.ward_id) != str(current_user.user_ward_id):
        raise HTTPException(status_code=403, detail="You can only edit records in your own ward")

    for field, value in request.model_dump(exclude_unset=True).items():
        setattr(record, field, value)
    record.entered_by = current_user.user_id
    db.commit()
    db.refresh(record)
    auto_assess_business(db, record)

    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "status_code": 200,
            "message": "Business record updated",
            "data": serialize(record, BusinessRecordResponse),
        },
    )


# ══════════════════════════════════════════════════════════════
# EXCEL IMPORT
# ══════════════════════════════════════════════════════════════
IMPORT_UPLOAD_DIR = "static/tax_imports"
os.makedirs(IMPORT_UPLOAD_DIR, exist_ok=True)


@router.post("/imports")
def upload_tax_survey_excel(
    tax_type: TaxType = Form(...),
    file: UploadFile = File(...),
    db=Depends(get_db),
    current_user=Depends(require_permission("validate_data")),
):
    if not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="Only .xlsx/.xls files are accepted")

    tmp_name = f"{uuid_lib.uuid4().hex[:8]}_{file.filename}"
    tmp_path = os.path.join(IMPORT_UPLOAD_DIR, tmp_name)
    with open(tmp_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        batch = import_survey_excel(
            db=db,
            file_path=tmp_path,
            filename=file.filename,
            ward_id=current_user.user_ward_id,
            tax_type=tax_type,
            uploaded_by_user_id=current_user.user_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        os.remove(tmp_path)

    return JSONResponse(
        status_code=201,
        content={
            "success": True,
            "status_code": 201,
            "message": f"{len(batch.rows)} rows parsed — review before committing",
            "data": serialize(batch, TaxImportBatchResponse),
        },
    )


@router.get("/imports/{batch_id}")
def get_import_batch(
    batch_id: UUID,
    db=Depends(get_db),
    current_user=Depends(require_permission("read_user")),
):
    batch = db.query(TaxImportBatchModel).filter(TaxImportBatchModel.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Import batch not found")

    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "status_code": 200,
            "message": "Import batch fetched successfully",
            "data": serialize(batch, TaxImportBatchResponse),
        },
    )


@router.put("/imports/rows/{row_id}")
def edit_import_row(
    row_id: UUID,
    request: TaxImportRowEditRequest,
    db=Depends(get_db),
    current_user=Depends(require_permission("validate_data")),
):
    row = db.query(TaxImportRowModel).filter(TaxImportRowModel.id == row_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Import row not found")
    _assert_ward_scope(current_user, row.batch.ward_id)

    if request.raw_data is not None:
        row.raw_data = {**row.raw_data, **request.raw_data}
    if request.phone_number is not None:
        row.phone_number = request.phone_number
        from model.user_model import UserModel
        from enums.tax_enums import ImportRowMatchStatus
        citizen = db.query(UserModel).filter(UserModel.user_phone_number == request.phone_number).first()
        if not citizen:
            row.matched_citizen_id = None
            row.match_status = ImportRowMatchStatus.NOT_REGISTERED
            row.error_message = "No citizen account with this phone number."
        elif str(citizen.ward_id) != str(row.batch.ward_id):
            row.matched_citizen_id = citizen.user_id
            row.match_status = ImportRowMatchStatus.WARD_MISMATCH
            row.error_message = "This phone number is registered under a different ward."
        else:
            row.matched_citizen_id = citizen.user_id
            row.match_status = ImportRowMatchStatus.MATCHED
            row.error_message = None
    if request.status is not None:
        row.status = request.status

    db.commit()
    db.refresh(row)

    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "status_code": 200,
            "message": "Import row updated",
            "data": serialize(row, TaxImportRowResponse),
        },
    )


@router.post("/imports/{batch_id}/approve-all")
def approve_all_matched_rows(
    batch_id: UUID,
    db=Depends(get_db),
    current_user=Depends(require_permission("validate_data")),
):
    batch = db.query(TaxImportBatchModel).filter(TaxImportBatchModel.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Import batch not found")
    if str(batch.ward_id) != str(current_user.user_ward_id):
        raise HTTPException(status_code=403, detail="You can only manage imports for your own ward")
    if batch.status == ImportBatchStatus.COMMITTED:
        raise HTTPException(status_code=400, detail="This batch has already been committed")

    approved_count = 0
    for row in batch.rows:
        if row.status == TaxImportRowStatus.PENDING and row.match_status == ImportRowMatchStatus.MATCHED:
            row.status = TaxImportRowStatus.APPROVED
            approved_count += 1
    db.commit()
    db.refresh(batch)

    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "status_code": 200,
            "message": f"{approved_count} row(s) approved. Rows needing correction were left for manual review.",
            "data": serialize(batch, TaxImportBatchResponse),
        },
    )


@router.post("/imports/{batch_id}/commit")
def commit_import_batch(
    batch_id: UUID,
    db=Depends(get_db),
    current_user=Depends(require_permission("validate_data")),
):
    batch = db.query(TaxImportBatchModel).filter(TaxImportBatchModel.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Import batch not found")
    _assert_ward_scope(current_user, batch.ward_id)
    if batch.status == ImportBatchStatus.COMMITTED:
        raise HTTPException(status_code=400, detail="This batch has already been committed")

    unresolved = [r for r in batch.rows if r.status == TaxImportRowStatus.PENDING]
    if unresolved:
        raise HTTPException(
            status_code=400,
            detail=f"{len(unresolved)} row(s) still need review (approve/reject) before committing",
        )

    try:
        commit_batch(db, batch, current_user.user_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "status_code": 200,
            "message": "Batch committed — approved rows are now live tax records",
            "data": serialize(batch, TaxImportBatchResponse),
        },
    )


# ══════════════════════════════════════════════════════════════
# ASSESSMENTS
# ══════════════════════════════════════════════════════════════
@router.post("/assessments/property/{property_id}")
def generate_property_tax(
    property_id: UUID,
    fiscal_year: str = Form(...),
    due_in_days: int = Form(90),
    db=Depends(get_db),
    current_user=Depends(require_permission("validate_data")),
):
    record = db.query(PropertyRecordModel).filter(PropertyRecordModel.id == property_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Property record not found")

    try:
        assessment = generate_property_assessment(
            db, record, fiscal_year, datetime.utcnow() + timedelta(days=due_in_days)
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return JSONResponse(
        status_code=201,
        content={
            "success": True,
            "status_code": 201,
            "message": "Property tax assessed",
            "data": serialize(assessment, TaxAssessmentResponse),
        },
    )


@router.get("/assessments/my")
def get_my_assessments(
    db=Depends(get_db),
    current_user=Depends(require_permission("read_user")),
):
    assessments = db.query(TaxAssessmentModel).filter(
        TaxAssessmentModel.citizen_id == current_user.user_id
    ).all()
    assessments = [apply_overdue_penalty(db, a) for a in assessments]

    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "status_code": 200,
            "message": "Your tax assessments",
            "total": len(assessments),
            "data": [serialize(a, TaxAssessmentResponse) for a in assessments],
        },
    )


@router.get("/assessments/ward")
def list_ward_assessments(
    tax_type: Optional[TaxType] = None,
    status: Optional[TaxAssessmentStatus] = None,
    db=Depends(get_db),
    current_user=Depends(require_permission("read_user")),
):
    query = db.query(TaxAssessmentModel).filter(
        TaxAssessmentModel.ward_id == current_user.user_ward_id
    )
    if tax_type:
        query = query.filter(TaxAssessmentModel.tax_type == tax_type)
    if status:
        query = query.filter(TaxAssessmentModel.status == status)

    assessments = query.order_by(TaxAssessmentModel.created_at.desc()).all()
    assessments = [apply_overdue_penalty(db, a) for a in assessments]

    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "status_code": 200,
            "message": "Ward tax assessments fetched successfully",
            "total": len(assessments),
            "data": [serialize(a, TaxAssessmentResponse) for a in assessments],
        },
    )


# ══════════════════════════════════════════════════════════════
# PAYMENTS — receipt PDF is issued the instant an assessment goes PAID,
# both here (manual/CASH) and in the Khalti callback below.
#
# FIX: issue_tax_receipt() uses Playwright's *sync* API internally
# (sync_playwright()). Playwright's sync API raises if it detects a
# running asyncio event loop in the current thread. record_tax_payment
# below is a plain `def` route, so FastAPI runs it in a threadpool with
# no event loop — issue_tax_receipt() works fine there. But the Khalti
# callback (verify_khalti_tax_payment) is `async def`, which DOES run
# on the event loop — so calling issue_tax_receipt() directly there
# always raised, silently, *after* assessment.status was already
# committed as PAID. That's why paid assessments were stuck with
# pdf_path = NULL forever. Fix: push it to a thread with
# run_in_threadpool, and never let a receipt-generation failure take
# down the payment flow itself (wrap in try/except + log).
# ══════════════════════════════════════════════════════════════
@router.post("/payments")
def record_tax_payment(
    request: TaxPaymentRequest,
    db=Depends(get_db),
    current_user=Depends(require_permission("read_user")),
):
    assessment = db.query(TaxAssessmentModel).filter(
        TaxAssessmentModel.id == request.assessment_id
    ).first()
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    if assessment.status == TaxAssessmentStatus.PAID:
        raise HTTPException(status_code=400, detail="This assessment is already paid")

    year = datetime.utcnow().year
    seq = db.query(TaxPaymentModel).filter(
        TaxPaymentModel.receipt_no.like(f"RCPT-{year}-%")
    ).count() + 1
    receipt_no = f"RCPT-{year}-{seq:06d}"

    payment = TaxPaymentModel(
        assessment_id=assessment.id,
        amount_paid=request.amount_paid,
        method=request.method,
        receipt_no=receipt_no,
        recorded_by=current_user.user_id,
    )
    db.add(payment)

    if float(request.amount_paid) >= float(assessment.total_due):
        assessment.status = TaxAssessmentStatus.PAID

    db.commit()
    db.refresh(payment)

    if assessment.status == TaxAssessmentStatus.PAID:
        # This route is sync (runs in a threadpool) so sync_playwright()
        # is safe here — but still guard it so a rendering/logo/stamp
        # problem never turns a successful payment into a 500.
        try:
            issue_tax_receipt(db, payment, issued_by_user_id=current_user.user_id)
        except Exception:
            logger.exception("Failed to issue tax receipt for payment %s", payment.id)

    return JSONResponse(
        status_code=201,
        content={
            "success": True,
            "status_code": 201,
            "message": "Payment recorded",
            "data": serialize(payment, TaxPaymentResponse),
        },
    )


@router.post("/payments/khalti/initiate")
async def initiate_khalti_tax_payment(
    request: KhaltiInitiateRequest,
    db=Depends(get_db),
    current_user=Depends(require_permission("read_user")),
):
    assessment = db.query(TaxAssessmentModel).filter(
        TaxAssessmentModel.id == request.assessment_id
    ).first()
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    if assessment.citizen_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="You can only pay your own assessment")
    if assessment.status == TaxAssessmentStatus.PAID:
        raise HTTPException(status_code=400, detail="This assessment is already paid")

    from model.user_model import UserModel
    citizen = db.query(UserModel).filter(UserModel.user_id == current_user.user_id).first()
    if not citizen:
        raise HTTPException(status_code=404, detail="Your account could not be found")

    year = datetime.utcnow().year
    seq = db.query(TaxPaymentModel).filter(
        TaxPaymentModel.receipt_no.like(f"RCPT-{year}-%")
    ).count() + 1
    receipt_no = f"RCPT-{year}-{seq:06d}"

    try:
        khalti_data = await initiate_khalti_payment(
            amount_rs=float(assessment.total_due),
            purchase_order_id=str(assessment.id),
            purchase_order_name=f"{assessment.tax_type.value} tax — FY {assessment.fiscal_year}",
            customer_name=citizen.user_nepali_name or citizen.user_name,
            customer_email=citizen.user_email,
            customer_phone=citizen.user_phone_number,
        )
    except ValueError as e:
        raise HTTPException(status_code=502, detail=str(e))

    payment = TaxPaymentModel(
        assessment_id=assessment.id,
        amount_paid=assessment.total_due,
        method=TaxPaymentMethod.KHALTI,
        receipt_no=receipt_no,
        recorded_by=current_user.user_id,
        pidx=khalti_data["pidx"],
        gateway_status="Pending",
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)

    return JSONResponse(
        status_code=201,
        content={
            "success": True,
            "status_code": 201,
            "message": "Redirect the citizen to payment_url to complete payment on Khalti",
            "data": KhaltiInitiateResponse(
                payment_url=khalti_data["payment_url"], pidx=khalti_data["pidx"]
            ).model_dump(),
        },
    )


# Public — no auth. Khalti's browser redirect calls back on this after
# the citizen completes (or cancels) payment on Khalti's hosted page.
@router.get("/payments/khalti/verify")
async def verify_khalti_tax_payment(pidx: str, db=Depends(get_db)):
    payment = db.query(TaxPaymentModel).filter(TaxPaymentModel.pidx == pidx).first()
    if not payment:
        return RedirectResponse(f"{FRONTEND_BASE_URL}/?tax_payment=not_found")

    try:
        khalti_data = await lookup_khalti_payment(pidx)
    except ValueError:
        return RedirectResponse(f"{FRONTEND_BASE_URL}/?tax_payment=verify_failed")

    status = khalti_data.get("status")
    payment.gateway_status = status or "Failed"
    payment.transaction_id = khalti_data.get("transaction_id")

    assessment = db.query(TaxAssessmentModel).filter(
        TaxAssessmentModel.id == payment.assessment_id
    ).first()

    if status == "Completed":
        if assessment and assessment.status != TaxAssessmentStatus.PAID:
            assessment.status = TaxAssessmentStatus.PAID
        db.commit()
        db.refresh(payment)

        # FIX: this route is `async def`, which runs on the event loop.
        # issue_tax_receipt() calls Playwright's sync_playwright() API,
        # which raises immediately if an event loop is already running
        # in this thread. Calling it directly here (the old code) meant
        # this line always threw — after the PAID commit above had
        # already gone through — leaving pdf_path permanently NULL and
        # also breaking this function's own redirect. run_in_threadpool
        # runs it in a worker thread with no event loop, where the sync
        # Playwright API works exactly like it does in the CASH path.
        # Idempotent — safe even if Khalti's callback fires more than once.
        try:
            await run_in_threadpool(issue_tax_receipt, db, payment)
        except Exception:
            logger.exception("Failed to issue tax receipt for payment %s", payment.id)

        # FIX: pass payment_id back through the redirect so the frontend
        # knows *which* payment just completed and can fetch + auto-open
        # its receipt immediately — mirrors how the birth-certificate flow
        # hands the citizen their PDF the instant it's issued, instead of
        # just showing a toast and making them hunt for a "View Receipt"
        # button in a list further down the page.
        return RedirectResponse(
            f"{FRONTEND_BASE_URL}/?tax_payment=success&payment_id={payment.id}"
        )

    db.commit()
    return RedirectResponse(f"{FRONTEND_BASE_URL}/?tax_payment=failed&reason={status}")


@router.get("/payments/{payment_id}/receipt")
def get_tax_payment_receipt(
    payment_id: UUID,
    db=Depends(get_db),
    current_user=Depends(require_permission("read_user")),
):
    """
    Returns the payment row including qr_path/pdf_path/receipt_issued_at
    so the frontend can render a "Download Receipt" button. Restricted to
    the citizen who paid, staff of that assessment's ward, or an Admin —
    same three-way check pattern used elsewhere in this router, just
    applied to a payment instead of a property/business record.

    FIX: added a lazy fallback. If an older payment is stuck with
    pdf_path = NULL (e.g. from the Khalti bug above, before this file
    was patched), retry generation on-demand here — this route is a
    plain `def`, so it runs in a threadpool and sync_playwright() is
    safe to call directly, no run_in_threadpool needed.
    """
    payment = db.query(TaxPaymentModel).filter(TaxPaymentModel.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    assessment = db.query(TaxAssessmentModel).filter(
        TaxAssessmentModel.id == payment.assessment_id
    ).first()
    is_admin = str(getattr(current_user, "user_role", "")).upper().endswith("ADMIN")
    is_owner = assessment and assessment.citizen_id == current_user.user_id
    is_ward_staff = assessment and str(assessment.ward_id) == str(current_user.user_ward_id)
    if not (is_admin or is_owner or is_ward_staff):
        raise HTTPException(status_code=403, detail="You don't have access to this receipt")

    if not payment.pdf_path and assessment and assessment.status == TaxAssessmentStatus.PAID:
        try:
            payment = issue_tax_receipt(db, payment, issued_by_user_id=current_user.user_id)
        except Exception:
            logger.exception("Retry receipt issuance failed for payment %s", payment.id)

    if not payment.pdf_path:
        raise HTTPException(status_code=400, detail="Receipt not issued yet for this payment")

    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "status_code": 200,
            "message": "Receipt fetched successfully",
            "data": serialize(payment, TaxPaymentResponse),
        },
    )


# Public — no auth, same reasoning as the birth-certificate QR verify
# endpoint: payment_id is the only lookup key and it's unguessable, so
# this is safe to expose without login. Response deliberately excludes
# phone/citizenship numbers — only what's printed on the receipt itself.
@router.get("/receipts/verify/{payment_id}")
def verify_tax_receipt(payment_id: UUID, db=Depends(get_db)):
    payment = db.query(TaxPaymentModel).filter(TaxPaymentModel.id == payment_id).first()
    if not payment or not payment.pdf_path:
        raise HTTPException(status_code=404, detail="Receipt not found")

    assessment = db.query(TaxAssessmentModel).filter(
        TaxAssessmentModel.id == payment.assessment_id
    ).first()

    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "status_code": 200,
            "message": "Receipt is valid",
            "data": {
                "receipt_no": payment.receipt_no,
                "amount_paid": float(payment.amount_paid),
                "method": payment.method.value,
                "paid_at": payment.paid_at.isoformat() if payment.paid_at else None,
                "tax_type": assessment.tax_type.value if assessment else None,
                "fiscal_year": assessment.fiscal_year if assessment else None,
                "citizen_name": assessment.citizen_name if assessment else None,
                "data_hash": payment.data_hash,
                "pdf_url": payment.pdf_path,   # new
            },
        },
    )


# ══════════════════════════════════════════════════════════════
# DISPUTES
# ══════════════════════════════════════════════════════════════
@router.post("/assessments/{assessment_id}/dispute")
def raise_dispute(
    assessment_id: UUID,
    request: TaxDisputeRequest,
    db=Depends(get_db),
    current_user=Depends(require_permission("write_form")),
):
    assessment = db.query(TaxAssessmentModel).filter(TaxAssessmentModel.id == assessment_id).first()
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    if assessment.citizen_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="You can only dispute your own assessment")

    dispute = TaxDisputeModel(
        assessment_id=assessment_id,
        citizen_id=current_user.user_id,
        reason=request.reason,
    )
    assessment.status = TaxAssessmentStatus.DISPUTED
    db.add(dispute)
    db.commit()
    db.refresh(dispute)

    return JSONResponse(
        status_code=201,
        content={
            "success": True,
            "status_code": 201,
            "message": "Dispute submitted — an officer will review your record",
            "data": serialize(dispute, TaxDisputeResponse),
        },
    )


@router.put("/disputes/{dispute_id}/resolve")
def resolve_dispute(
    dispute_id: UUID,
    request: TaxDisputeResolveRequest,
    db=Depends(get_db),
    current_user=Depends(require_permission("validate_data")),
):
    dispute = db.query(TaxDisputeModel).filter(TaxDisputeModel.id == dispute_id).first()
    if not dispute:
        raise HTTPException(status_code=404, detail="Dispute not found")

    dispute.status = request.status
    dispute.resolution_note = request.resolution_note
    dispute.resolved_by = current_user.user_id
    dispute.resolved_at = datetime.utcnow()

    if request.status == TaxDisputeStatus.RESOLVED:
        dispute.assessment.status = TaxAssessmentStatus.ASSESSED

    db.commit()
    db.refresh(dispute)

    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "status_code": 200,
            "message": "Dispute resolved",
            "data": serialize(dispute, TaxDisputeResponse),
        },
    )