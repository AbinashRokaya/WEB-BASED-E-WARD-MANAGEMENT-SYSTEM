# router/complaint_router.py
import uuid as uuid_lib
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from auth.current_user import require_permission
from database.db import get_db
from enums.complaint_enum import ComplaintCategory, ComplaintPriority, ComplaintStatus
from model.complaint_model import ComplaintModel, ComplaintRejectModel
from model.user_model import UserModel
from model.ward_model import WardModel
from schema.complaint_schema import (
    ComplaintDocumentsResponse, ComplaintRejectRequest, ComplaintRejectResponse,
    ComplaintResponse, ComplaintResponseAll, ComplaintStatsResponse,
    UpdateComplaintRequest,
)

import cloudinary.uploader
import config.cloudinary_config  # noqa: F401  (runs cloudinary.config() on import)

router = APIRouter(
    prefix="/v1/complaint",
    tags=["complaint"]
)


def serialize(obj, schema):
    return schema.from_orm(obj).model_dump(mode="json")


ALLOWED_COMPLAINT_DOC_TYPES = {"image/png", "image/jpeg", "image/jpg", "image/webp", "application/pdf"}

# Cloudinary "folder" prefix — mirrors what COMPLAINT_UPLOAD_DIR did for
# the local static/ directory.
CLOUDINARY_COMPLAINT_FOLDER = "complaint"


def _save_complaint_document(complaint_id: UUID, file: UploadFile, suffix: str) -> str:
    """
    Uploads a complaint attachment to Cloudinary and returns the full
    secure (https) URL. Previously wrote to static/complaint/{id}/ and
    returned a path relative to the /static mount; the DB column now
    stores the full URL directly.
    """
    if file.content_type not in ALLOWED_COMPLAINT_DOC_TYPES:
        raise HTTPException(status_code=400, detail="Only PNG/JPEG/WEBP/PDF files allowed")

    resource_type = "raw" if file.content_type == "application/pdf" else "image"
    public_id = f"{CLOUDINARY_COMPLAINT_FOLDER}/{complaint_id}/{suffix}_{uuid_lib.uuid4().hex[:8]}"

    try:
        upload_result = cloudinary.uploader.upload(
            file.file,
            public_id=public_id,
            resource_type=resource_type,
            overwrite=False,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Attachment upload failed: {e}")

    return upload_result["secure_url"]


def _generate_complaint_number(db) -> str:
    year = 2083  # replace with your bikram_sambat_year() helper if you have one
    count = db.query(ComplaintModel).count()
    sequence = str(count + 1).zfill(4)
    candidate = f"CMP-{year}-{sequence}"
    while db.query(ComplaintModel).filter(ComplaintModel.complaint_number == candidate).first():
        sequence = str(int(sequence) + 1).zfill(4)
        candidate = f"CMP-{year}-{sequence}"
    return candidate


@router.post("/")
def create_complaint(
    complaint_category: ComplaintCategory = Form(...),
    subject: str = Form(...),
    description: str = Form(...),
    location: Optional[str] = Form(None),
    attachment_1: Optional[UploadFile] = File(None),
    attachment_2: Optional[UploadFile] = File(None),
    attachment_3: Optional[UploadFile] = File(None),
    db=Depends(get_db),
    current_user=Depends(require_permission("read_user")),
):
    try:
        ward = db.query(WardModel).filter(WardModel.ward_id == current_user.user_ward_id).first()
        if not ward:
            raise HTTPException(status_code=404, detail="Ward not found")

        user = db.query(UserModel).filter(UserModel.user_id == current_user.user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        complaint = ComplaintModel(
            complaint_number=_generate_complaint_number(db),
            complaint_ward_id=current_user.user_ward_id,
            complaint_submitted_by=current_user.user_id,
            complaint_status=ComplaintStatus.SUBMITTED,
            complaint_category=complaint_category,
            subject=subject,
            description=description,
            location=location,
        )
        db.add(complaint)
        db.flush()

        if attachment_1:
            complaint.attachment_1_path = _save_complaint_document(complaint.complaint_id, attachment_1, "attachment_1")
        if attachment_2:
            complaint.attachment_2_path = _save_complaint_document(complaint.complaint_id, attachment_2, "attachment_2")
        if attachment_3:
            complaint.attachment_3_path = _save_complaint_document(complaint.complaint_id, attachment_3, "attachment_3")

        db.commit()
        db.refresh(complaint)

        return JSONResponse(
            status_code=201,
            content={
                "success": True,
                "status_code": 201,
                "message": "Complaint submitted successfully",
                "data": serialize(complaint, ComplaintResponse),
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/all")
def get_all_complaints(db=Depends(get_db), current_user=Depends(require_permission("read_user"))):
    """Citizen's own complaints."""
    try:
        complaints = (
            db.query(ComplaintModel)
            .filter(
                ComplaintModel.complaint_submitted_by == current_user.user_id,
                ComplaintModel.complaint_status != ComplaintStatus.DRAFT,
            )
            .all()
        )

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "status_code": 200,
                "message": "Complaints fetched successfully",
                "total": len(complaints),
                "data": [
                    ComplaintResponseAll.model_validate(c).model_dump(mode="json")
                    for c in complaints
                ],
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/officer/all")
def get_officer_complaints(db=Depends(get_db), current_user=Depends(require_permission("read_user"))):
    """Officer's queue — complaints waiting for the first-stage decision."""
    try:
        complaints = (
            db.query(ComplaintModel)
            .filter(
                ComplaintModel.complaint_ward_id == current_user.user_ward_id,
                ComplaintModel.complaint_status == ComplaintStatus.SUBMITTED,
            )
            .all()
        )
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "status_code": 200,
                "message": "Complaints fetched successfully",
                "total": len(complaints),
                "data": [ComplaintResponseAll.model_validate(c).model_dump(mode="json") for c in complaints],
            },
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/")
def get_all_registrations(
    status: ComplaintStatus = None,
    ward_id: UUID = None,
    db=Depends(get_db)
):
    try:
        query = db.query(ComplaintModel).filter(ComplaintModel.complaint_status != ComplaintStatus.DRAFT)

        if status:
            query = query.filter(ComplaintModel.complaint_status == status)
        if ward_id:
            query = query.filter(ComplaintModel.complaint_ward_id == ward_id)

        complaints = query.all()

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "status_code": 200,
                "message": "Complaints fetched successfully",
                "total": len(complaints),
                "data": [serialize(c, ComplaintResponseAll) for c in complaints]
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{complaint_id}")
def get_complaint(complaint_id: UUID, db=Depends(get_db)):
    try:
        complaint = db.query(ComplaintModel).filter(
            ComplaintModel.complaint_id == complaint_id
        ).first()

        if not complaint:
            raise HTTPException(status_code=404, detail="Complaint not found")

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "status_code": 200,
                "message": "Complaint fetched successfully",
                "data": serialize(complaint, ComplaintResponse)
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{complaint_id}")
def update_complaint(
    complaint_id: UUID,
    request: UpdateComplaintRequest,
    db=Depends(get_db)
):
    try:
        complaint = db.query(ComplaintModel).filter(
            ComplaintModel.complaint_id == complaint_id
        ).first()
        if not complaint:
            raise HTTPException(status_code=404, detail="Complaint not found")

        if complaint.complaint_status in (ComplaintStatus.RESOLVED, ComplaintStatus.REJECTED):
            raise HTTPException(status_code=400, detail="Closed complaints cannot be edited")

        data = request.model_dump(exclude_unset=True)
        for field, value in data.items():
            setattr(complaint, field, value)

        db.commit()
        db.refresh(complaint)

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "status_code": 200,
                "message": "Complaint updated successfully",
                "data": serialize(complaint, ComplaintResponse)
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# ══════════════════════════════════════════════
# OFFICER STAGE ONLY — SUBMITTED -> APPROVED / REJECTED
# Secretary (APPROVED -> VERIFIED) lives in ward_secretary_router.py
# Chairperson (VERIFIED -> RESOLVED) lives in ward_chairperson_router.py
# ══════════════════════════════════════════════

@router.post("/{complaint_id}/reject")
def reject_complaint(
    complaint_id: UUID,
    request: ComplaintRejectRequest,
    db=Depends(get_db),
    current_user=Depends(require_permission("read_user")),
):
    try:
        complaint = db.query(ComplaintModel).filter(
            ComplaintModel.complaint_id == complaint_id
        ).first()
        if not complaint:
            raise HTTPException(status_code=404, detail="Complaint not found")

        if complaint.complaint_status != ComplaintStatus.SUBMITTED:
            raise HTTPException(status_code=400, detail="Only SUBMITTED complaints can be rejected here")

        complaint.complaint_status = ComplaintStatus.REJECTED

        reject = ComplaintRejectModel(
            complaint_id=complaint_id,
            reject_text=request.reject_text,
            rejected_by=current_user.user_id,
        )
        db.add(reject)
        db.commit()
        db.refresh(reject)

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "status_code": 200,
                "message": "Complaint rejected successfully",
                "data": serialize(reject, ComplaintRejectResponse)
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{complaint_id}/approve")
def approve_complaint(complaint_id: UUID, db=Depends(get_db)):
    """Officer stage — SUBMITTED -> APPROVED."""
    try:
        complaint = db.query(ComplaintModel).filter(
            ComplaintModel.complaint_id == complaint_id
        ).first()
        if not complaint:
            raise HTTPException(status_code=404, detail="Complaint not found")

        if complaint.complaint_status != ComplaintStatus.SUBMITTED:
            raise HTTPException(status_code=400, detail="Only SUBMITTED complaints can be approved")

        complaint.complaint_status = ComplaintStatus.APPROVED
        db.commit()

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "status_code": 200,
                "message": "Complaint approved successfully",
                "data": None
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{complaint_id}/upload-documents")
def upload_complaint_documents(
    complaint_id: UUID,
    attachment_1: Optional[UploadFile] = File(None),
    attachment_2: Optional[UploadFile] = File(None),
    attachment_3: Optional[UploadFile] = File(None),
    db=Depends(get_db),
):
    complaint = db.query(ComplaintModel).filter(
        ComplaintModel.complaint_id == complaint_id
    ).first()
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")

    if not any([attachment_1, attachment_2, attachment_3]):
        raise HTTPException(status_code=400, detail="No file provided")

    try:
        if attachment_1:
            complaint.attachment_1_path = _save_complaint_document(complaint_id, attachment_1, "attachment_1")
        if attachment_2:
            complaint.attachment_2_path = _save_complaint_document(complaint_id, attachment_2, "attachment_2")
        if attachment_3:
            complaint.attachment_3_path = _save_complaint_document(complaint_id, attachment_3, "attachment_3")

        db.commit()
        db.refresh(complaint)

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "status_code": 200,
                "message": "Complaint documents uploaded successfully",
                "data": ComplaintDocumentsResponse.model_validate(complaint).model_dump(mode="json"),
            },
        )

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ward/{ward_id}/stats")
def get_complaint_stats(ward_id: UUID, db=Depends(get_db)):
    try:
        base = db.query(ComplaintModel).filter(ComplaintModel.complaint_ward_id == ward_id)
        total = base.count()

        by_status = {s.value: base.filter(ComplaintModel.complaint_status == s).count() for s in ComplaintStatus}
        by_category = {c.value: base.filter(ComplaintModel.complaint_category == c).count() for c in ComplaintCategory}

        stats = ComplaintStatsResponse(total=total, by_status=by_status, by_category=by_category, escalated=0)

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "status_code": 200,
                "message": "Complaint statistics fetched successfully",
                "data": stats.model_dump(mode="json"),
            },
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))