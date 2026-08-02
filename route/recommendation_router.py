# router/recommendation_router.py
import json
import os
import shutil
import uuid as uuid_lib
from uuid import UUID
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from fastapi.responses import FileResponse, JSONResponse
from auth.current_user import require_permission
from database.db import get_db
from enums.recommendation_enum import RecommendationStatus, RecommendationLetterType
from model.recommendation_model import RecommendationLetterModel, RecommendationRejectModel
from model.user_model import UserModel
from model.ward_model import WardModel
from schema.recommendation_schema import (
    RecommendationLetterRequest, RecommendationLetterResponse,
    UpdateRecommendationRequest, RejectRequest, RejectResponse,
)

from fastapi import BackgroundTasks
from services.recommendation_certificate_service import issue_certificate_for_recommendation_letter
from services.email_service import send_recommendation_certificate_ready_email
from schema.certificate_schema import CertificateResponse, VerifyCertificateResponse

BACKEND_BASE_URL = os.environ.get("BACKEND_BASE_URL", "http://localhost:8000")

router = APIRouter(prefix="/v1/recommendation-letter", tags=["recommendation-letter"])

ALLOWED_DOC_TYPES = {"image/png", "image/jpeg", "image/jpg", "image/webp", "application/pdf"}
UPLOAD_DIR = "static/recommendation_letter"

# Server-side mirror of the frontend's DOCUMENT_REQUIREMENTS — which
# letter types require a supporting document beyond citizenship.
# Keep this in sync with RecommendationLetter.jsx's DOCUMENT_REQUIREMENTS.
SUPPORTING_DOCUMENT_REQUIRED = {
    RecommendationLetterType.RESIDENCE_PROOF: True,
    RecommendationLetterType.UNMARRIED_STATUS: False,
    RecommendationLetterType.CHARACTER_CERTIFICATE: False,
    RecommendationLetterType.INCOME_STATEMENT: True,
    RecommendationLetterType.RELATIONSHIP_PROOF: True,
    RecommendationLetterType.LAND_OWNERSHIP_PROOF: True,
    RecommendationLetterType.OTHER: False,
}

# Letter types where the applicant may legitimately request the letter from
# a ward OTHER than their own registered ward (e.g. proving they currently
# live somewhere different from where their citizenship/account is
# registered). For every other letter type, the address and
# register_ward_id are derived ENTIRELY server-side from
# current_user.user_ward_id — the client never supplies them, so there is
# nothing for a citizen (or a modified frontend request) to get wrong.
# Keep this in sync with the frontend's LETTER_TYPES_ALLOWING_DIFFERENT_WARD.
LETTER_TYPES_ALLOWING_DIFFERENT_WARD = {RecommendationLetterType.RESIDENCE_PROOF}


def _get_user_ward_or_404(db, current_user) -> WardModel:
    """Look up the logged-in citizen's own ward. Raises 422/404 with a
    clear message if the account has no ward on file or it's been deleted
    — this is the single source of truth for "my own ward" everywhere in
    this router."""
    if not current_user.user_ward_id:
        raise HTTPException(
            status_code=422,
            detail="Your account has no registered ward on file. Please contact an administrator.",
        )
    ward = db.query(WardModel).filter(WardModel.ward_id == current_user.user_ward_id).first()
    if not ward:
        raise HTTPException(
            status_code=404,
            detail="Your registered ward could not be found. Please contact an administrator.",
        )
    return ward


def _address_from_ward(ward: WardModel, tole: str = "") -> dict:
    """Builds the address dict (matching RecommendationLetterModel's
    address columns) entirely from a WardModel row, so the stored address
    always reflects real ward data rather than whatever a client sent."""
    return {
        "applicant_province": ward.ward_province,
        "applicant_district": ward.ward_district,
        "applicant_municipality": ward.ward_municipality,
        "applicant_ward_number": ward.ward_no,
        "applicant_tole": tole or "",
        "ward_nepali_province": ward.ward_nepali_province,
        "ward_nepali_district": ward.ward_nepali_district,
        "ward_nepali_municipality": ward.ward_nepali_municipality,
        "ward_nepali_name": ward.ward_nepali_name,
        "ward_type": ward.ward_type,
    }


def _save_document(letter_id: UUID, file: UploadFile, suffix: str) -> str:
    if file.content_type not in ALLOWED_DOC_TYPES:
        raise HTTPException(status_code=400, detail="Only PNG/JPEG/WEBP/PDF files allowed")
    ext = os.path.splitext(file.filename)[1] or ".png"
    letter_dir = os.path.join(UPLOAD_DIR, str(letter_id))
    os.makedirs(letter_dir, exist_ok=True)
    filename = f"{suffix}_{uuid_lib.uuid4().hex[:8]}{ext}"
    filepath = os.path.join(letter_dir, filename)
    with open(filepath, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    return f"recommendation_letter/{letter_id}/{filename}"


# ── NEW: the frontend calls this on mount to get the citizen's own address
# straight from the backend, using nothing but the session cookie
# (require_permission resolves current_user the same way every other
# endpoint here does). This is what the frontend renders read-only —
# there is no client-side "figure out my ward from a wards list + a
# currentUser prop" step anymore, which is exactly what was breaking
# (the prop was never being passed down from CertificateManager).
@router.get("/my-address")
def get_my_recommendation_address(
    db=Depends(get_db),
    current_user=Depends(require_permission("read_user")),
):
    ward = _get_user_ward_or_404(db, current_user)
    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "status_code": 200,
            "message": "Address fetched successfully",
            "data": {
                "register_ward_id": str(ward.ward_id),
                "ward_no": ward.ward_no,
                "ward_name": ward.ward_name,
                **_address_from_ward(ward),
            },
        },
    )


@router.post("/")
def create_recommendation_letter(
    letter: str = Form(...),   # JSON string -> RecommendationLetterRequest
    applicant_citizenship_front: Optional[UploadFile] = File(None),
    applicant_citizenship_back: Optional[UploadFile] = File(None),
    supporting_document: Optional[UploadFile] = File(None),
    db=Depends(get_db),
    current_user=Depends(require_permission("read_user")),
):
    try:
        try:
            data = RecommendationLetterRequest.model_validate(json.loads(letter))
        except (json.JSONDecodeError, ValidationError) as e:
            raise HTTPException(status_code=422, detail=f"Invalid JSON in form field: {e}")

        # ── Address / ward resolution — ENTIRELY server-side ───────────
        #
        # For every letter type EXCEPT the ones in
        # LETTER_TYPES_ALLOWING_DIFFERENT_WARD, we ignore whatever
        # register_ward_id/address the client sent and derive both from
        # current_user.user_ward_id instead. The frontend fetches the
        # same data from GET /my-address above purely for display — it
        # is never the source of truth the backend trusts. This closes
        # off any path (typo, tampered request, stale form state) where
        # a citizen's letter could end up routed to a ward that has no
        # way to verify them.
        #
        # RESIDENCE_PROOF is the one legitimate exception: an applicant
        # may really need a DIFFERENT ward (where they currently live) to
        # certify residence. For that case only, we trust the client's
        # register_ward_id/address, but still verify the ward exists.
        only_tole = (data.address.applicant_tole or "").strip() if data.address else ""

        if (
            data.letter_type in LETTER_TYPES_ALLOWING_DIFFERENT_WARD
            and data.register_ward_id != current_user.user_ward_id
        ):
            ward = db.query(WardModel).filter(WardModel.ward_id == data.register_ward_id).first()
            if not ward:
                raise HTTPException(status_code=404, detail="Selected ward not found")
            register_ward_id = ward.ward_id
            address_dict = data.address.model_dump()
        else:
            ward = _get_user_ward_or_404(db, current_user)
            register_ward_id = ward.ward_id
            address_dict = _address_from_ward(ward, tole=only_tole)

        # Citizenship is required both sides, for every letter type.
        if not applicant_citizenship_front or not applicant_citizenship_back:
            raise HTTPException(
                status_code=422,
                detail="Both sides of the applicant's citizenship document are required.",
            )

        # Whether a supporting document is required (and which one) depends
        # on the selected letter type — enforced here too, not just on the
        # frontend, since form submissions can bypass client-side checks.
        if SUPPORTING_DOCUMENT_REQUIRED.get(data.letter_type, False) and not supporting_document:
            raise HTTPException(
                status_code=422,
                detail=f"A supporting document is required for {data.letter_type.value}.",
            )

        letter_row = RecommendationLetterModel(
            register_ward_id=register_ward_id,
            register_submitted_by=current_user.user_id,
            register_status=RecommendationStatus.SUBMITTED,
            letter_type=data.letter_type,
            letter_type_other=data.letter_type_other,
            applicant_full_name_np=data.applicant_full_name_np,
            applicant_full_name_en=data.applicant_full_name_en,
            applicant_citizenship_no=data.applicant_citizenship_no,
            applicant_contact_no=data.applicant_contact_no,
            purpose=data.purpose,
            **address_dict,
        )
        db.add(letter_row)
        db.flush()

        letter_row.applicant_citizenship_front_path = _save_document(
            letter_row.letter_id, applicant_citizenship_front, "citizenship_front"
        )
        letter_row.applicant_citizenship_back_path = _save_document(
            letter_row.letter_id, applicant_citizenship_back, "citizenship_back"
        )
        if supporting_document:
            letter_row.supporting_document_path = _save_document(
                letter_row.letter_id, supporting_document, "supporting_doc"
            )

        db.commit()
        db.refresh(letter_row)

        return JSONResponse(
            status_code=201,
            content={
                "success": True,
                "status_code": 201,
                "message": "Recommendation letter request submitted successfully",
                "data": RecommendationLetterResponse.model_validate(letter_row).model_dump(mode="json"),
            },
        )

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# ── This is the citizen's OWN "my submissions" list (CERTIFICATE_TYPES.
# recommendation on the frontend calls apiBase + "/all" for exactly this).
#
# IMPORTANT — this must NOT mirror birth's /all filter. Birth's /all
# filters on register_ward_id == current_user.user_ward_id, which works
# for birth because register_ward_id there IS the submitting officer's
# own ward. For recommendation letters, register_ward_id is whichever
# ward the letter was ultimately routed to (almost always the applicant's
# own ward now, occasionally a different one for RESIDENCE_PROOF) — it
# has no fixed relationship to the submitting citizen's own ward, so
# filtering on it (as a previous version of this endpoint did) matches
# nothing for almost every real user, which is exactly why "my
# submissions" showed empty.
#
# The correct match is who actually submitted it — register_submitted_by
# == current_user.user_id, same identity field the ward-chairperson
# endpoints use to find the submitter's email. We also return every
# non-DRAFT status (SUBMITTED, VERIFIED, CERTIFICATE_ISSUED, REJECTED),
# not just SUBMITTED — a citizen's own list shouldn't lose a letter the
# moment it gets verified or a certificate is issued for it.
@router.get("/all")
def get_all_recommendation_letters(
    db=Depends(get_db),
    current_user=Depends(require_permission("read_user")),
):
    try:
        letters = (
            db.query(RecommendationLetterModel)
            .filter(
                RecommendationLetterModel.register_submitted_by == current_user.user_id,
                RecommendationLetterModel.register_status != RecommendationStatus.DRAFT,
            )
            .all()
        )

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "status_code": 200,
                "message": "Recommendation letters fetched successfully",
                "total": len(letters),
                "data": [
                    RecommendationLetterResponse.model_validate(l).model_dump(mode="json")
                    for l in letters
                ],
            },
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Every letter actually inside a given ward, regardless of status — for
# ward-secretary/chairperson staff who need the full history for their
# own ward (SUBMITTED, VERIFIED, CERTIFICATE_ISSUED, REJECTED), keyed by
# the applicant's chosen ward (register_ward_id), not the staff member's
# own ward — this is intentionally different scoping from /all above.
@router.get("/ward/all")
def get_all_ward_chairperson_recommendation_letters(
    db=Depends(get_db),
    current_user=Depends(require_permission("read_user")),
):
    try:
        letters = (
            db.query(RecommendationLetterModel)
            .filter(RecommendationLetterModel.register_ward_id == current_user.user_ward_id)
            .all()
        )
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "status_code": 200,
                "message": "Recommendation letters fetched successfully",
                "total": len(letters),
                "data": [
                    RecommendationLetterResponse.model_validate(l).model_dump(mode="json")
                    for l in letters
                ],
            },
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Mirrors BirthRegistrationModel's plain GET "/" ──────────────────────
# Open list (no baked-in ward scoping) with optional status / ward_id
# query params — same shape as birth's GET "/".
@router.get("/")
def get_recommendation_letters(
    status: RecommendationStatus = None,
    ward_id: UUID = None,
    db=Depends(get_db),
):
    try:
        query = db.query(RecommendationLetterModel)

        if status:
            query = query.filter(RecommendationLetterModel.register_status == status)
        if ward_id:
            query = query.filter(RecommendationLetterModel.register_ward_id == ward_id)

        letters = query.all()

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "status_code": 200,
                "message": "Recommendation letters fetched successfully",
                "total": len(letters),
                "data": [
                    RecommendationLetterResponse.model_validate(l).model_dump(mode="json")
                    for l in letters
                ],
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{letter_id}")
def get_recommendation_letter(letter_id: UUID, db=Depends(get_db)):
    letter = db.query(RecommendationLetterModel).filter(
        RecommendationLetterModel.letter_id == letter_id
    ).first()
    if not letter:
        raise HTTPException(status_code=404, detail="Letter not found")
    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "status_code": 200,
            "message": "Letter fetched successfully",
            "data": RecommendationLetterResponse.model_validate(letter).model_dump(mode="json"),
        },
    )


@router.put("/{letter_id}")
def update_recommendation_letter(
    letter_id: UUID,
    request: UpdateRecommendationRequest,
    db=Depends(get_db),
):
    letter = db.query(RecommendationLetterModel).filter(
        RecommendationLetterModel.letter_id == letter_id
    ).first()
    if not letter:
        raise HTTPException(status_code=404, detail="Letter not found")

    if letter.register_status == RecommendationStatus.APPROVED:
        raise HTTPException(status_code=400, detail="Approved letters cannot be edited")

    for field, value in request.model_dump(exclude_unset=True).items():
        setattr(letter, field, value)

    db.commit()
    db.refresh(letter)

    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "status_code": 200,
            "message": "Letter updated successfully",
            "data": RecommendationLetterResponse.model_validate(letter).model_dump(mode="json"),
        },
    )


@router.post("/{letter_id}/approve")
def approve_letter(letter_id: UUID, db=Depends(get_db)):
    letter = db.query(RecommendationLetterModel).filter(
        RecommendationLetterModel.letter_id == letter_id
    ).first()
    if not letter:
        raise HTTPException(status_code=404, detail="Letter not found")
    if letter.register_status != RecommendationStatus.SUBMITTED:
        raise HTTPException(status_code=400, detail="Only SUBMITTED letters can be approved")

    letter.register_status = RecommendationStatus.APPROVED
    db.commit()

    return JSONResponse(
        status_code=200,
        content={"success": True, "status_code": 200, "message": "Letter approved", "data": None},
    )


@router.post("/{letter_id}/reject")
def reject_letter(letter_id: UUID, request: RejectRequest, db=Depends(get_db)):
    letter = db.query(RecommendationLetterModel).filter(
        RecommendationLetterModel.letter_id == letter_id
    ).first()
    if not letter:
        raise HTTPException(status_code=404, detail="Letter not found")
    if letter.register_status != RecommendationStatus.SUBMITTED:
        raise HTTPException(status_code=400, detail="Only SUBMITTED letters can be rejected")

    letter.register_status = RecommendationStatus.REJECTED
    reject = RecommendationRejectModel(letter_id=letter_id, reject_text=request.reject_text)
    db.add(reject)
    db.commit()
    db.refresh(reject)

    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "status_code": 200,
            "message": "Letter rejected successfully",
            "data": RejectResponse.model_validate(reject).model_dump(mode="json"),
        },
    )

@router.post("/{letter_id}/issue-certificate")
def issue_recommendation_certificate(
    letter_id: UUID,
    background_tasks: BackgroundTasks,
    db=Depends(get_db),
    current_user=Depends(require_permission("issue_certificate")),
):
    letter = db.query(RecommendationLetterModel).filter(
        RecommendationLetterModel.letter_id == letter_id
    ).first()
    if not letter:
        raise HTTPException(status_code=404, detail="Letter not found")

    if letter.register_status != RecommendationStatus.SUBMITTED:
        raise HTTPException(status_code=400, detail="Only SUBMITTED letters can be issued a certificate")

    try:
        certificate = issue_certificate_for_recommendation_letter(letter, db, current_user.user_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    submitted_by = letter.submitted_by_user
    submitted_by_email = getattr(submitted_by, "user_email", None) if submitted_by else None

    if submitted_by_email:
        download_url = f"{BACKEND_BASE_URL}/v1/recommendation-letter/{letter.letter_id}/certificate/download"
        background_tasks.add_task(
            send_recommendation_certificate_ready_email,
            submitted_by_email,
            letter.applicant_full_name_en,
            certificate.certificate_no,
            download_url,
        )

    return JSONResponse(
        status_code=201,
        content={
            "success": True,
            "status_code": 201,
            "message": "Certificate issued successfully",
            "data": CertificateResponse.model_validate(certificate).model_dump(mode="json"),
        },
    )

@router.get("/{letter_id}/certificate/download")
def download_recommendation_certificate(letter_id: UUID, db=Depends(get_db)):
    letter = db.query(RecommendationLetterModel).filter(
        RecommendationLetterModel.letter_id == letter_id
    ).first()
    if not letter or not letter.certificate:
        raise HTTPException(status_code=404, detail="Certificate not found")

    pdf_path = os.path.join("static", letter.certificate.pdf_path)
    if not os.path.exists(pdf_path):
        raise HTTPException(status_code=404, detail="Certificate file missing on server")

    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{letter.certificate.certificate_no}.pdf"'},
    )

@router.get("/certificate/verify/{cert_id}", response_model=None)
def verify_recommendation_certificate(cert_id: UUID, db=Depends(get_db)):
    from model.recommendation_model import RecommendationCertificateModel

    certificate = db.query(RecommendationCertificateModel).filter(
        RecommendationCertificateModel.cert_id == cert_id
    ).first()
    if not certificate:
        raise HTTPException(status_code=404, detail="Certificate not found")

    letter = certificate.letter
    return JSONResponse(
        status_code=200,
        content=VerifyCertificateResponse(
            valid=certificate.is_valid,
            certificate_no=certificate.certificate_no,
            child_full_name=letter.applicant_full_name_en,  # generic field name, reused across cert types
            register_status=letter.register_status.value,
            issued_date=certificate.created_at,
            revoked_reason=certificate.revoked_reason,
        ).model_dump(mode="json"),
    )

@router.get("/officer/all")
def get_officer_recommendation_letters(
    db=Depends(get_db),
    current_user=Depends(require_permission("read_user")),
):
    try:
        letters = (
            db.query(RecommendationLetterModel)
            .filter(
                RecommendationLetterModel.register_ward_id == current_user.user_ward_id,
                RecommendationLetterModel.register_status == RecommendationStatus.SUBMITTED,
            )
            .all()
        )
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "status_code": 200,
                "message": "Recommendation letters fetched successfully",
                "total": len(letters),
                "data": [
                    RecommendationLetterResponse.model_validate(l).model_dump(mode="json")
                    for l in letters
                ],
            },
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))