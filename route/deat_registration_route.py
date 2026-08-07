# router/death_registration_router.py
import json
import logging
import os
import uuid as uuid_lib
from typing import Optional
from uuid import UUID

from fastapi import (
    APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile,
)
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from auth.current_user import require_permission
from database.db import get_db
from enums.death_enum import DeathRegistrationStatus
from model.death_registration_model import (
    DeathAddressModel, DeathCertificateModel, DeathDetailModel,
    DeathRegistrationModel, DeathRejectModel, DeceasedModel, InformantModel,
)
from model.user_model import UserModel
from model.ward_model import WardModel
from schema.certificate_schema import CertificateResponse, VerifyCertificateResponse
from schema.death_schema import (
    DeathAddressRequest, DeathDetailRequest, DeathRegistrationDocumentsResponse,
    DeathRegistrationResponse, DeathRegistrationResponseAll, DeathRejectRequest,
    DeathRejectResponse, DeceasedRequest, InformantRequest, InformantResponse,
    UpdateDeathAddressRequest, UpdateDeathRegistrationRequest,
    UpdateInformantRequest,
)
from services.death_certificate_service import issue_certificate_for_death_registration
from services.email_service import send_certificate_ready_email
from utils.certificate_download import stream_certificate_pdf

import cloudinary.uploader
import config.cloudinary_config  # noqa: F401  (runs cloudinary.config() on import)

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/v1/death-registration",
    tags=["death-registration"]
)

BACKEND_BASE_URL = os.environ.get("BACKEND_BASE_URL", "http://localhost:8000")


def serialize(obj, schema):
    return schema.from_orm(obj).model_dump(mode="json")


ALLOWED_DEATH_DOC_TYPES = {"image/png", "image/jpeg", "image/jpg", "image/webp", "application/pdf"}

# Cloudinary "folder" prefix — mirrors what DEATH_UPLOAD_DIR did for the
# local static/ directory.
CLOUDINARY_DEATH_FOLDER = "death_registration"


def _save_death_document(registration_id: UUID, file: UploadFile, suffix: str) -> str:
    """
    Uploads a death-registration document to Cloudinary and returns the
    full secure (https) URL. Previously wrote to
    static/death_registration/{id}/ and returned a path relative to the
    /static mount; the DB column now stores the full URL directly.
    """
    if file.content_type not in ALLOWED_DEATH_DOC_TYPES:
        raise HTTPException(status_code=400, detail="Only PNG/JPEG/WEBP/PDF files allowed")

    resource_type = "raw" if file.content_type == "application/pdf" else "image"
    public_id = f"{CLOUDINARY_DEATH_FOLDER}/{registration_id}/{suffix}_{uuid_lib.uuid4().hex[:8]}"

    try:
        upload_result = cloudinary.uploader.upload(
            file.file,
            public_id=public_id,
            resource_type=resource_type,
            overwrite=False,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Document upload failed: {e}")

    return upload_result["secure_url"]


def _get_user_ward_or_404(db, current_user) -> WardModel:
    """Look up the logged-in citizen's own ward — same pattern as
    birth_registration_router.py and recommendation_router.py."""
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


def _deceased_address_from_ward(ward: WardModel, tole: str = "") -> dict:
    """Builds ONLY the deceased_* + ward_nepali_* fields from a WardModel
    row. death_place_* and informant_* fields are intentionally NOT
    covered here — those addresses are independent of the submitting
    account's own ward (place of death is frequently a hospital in a
    different ward; the informant can live anywhere) and stay
    client-supplied, same as before."""
    return {
        "deceased_province": ward.ward_province,
        "deceased_district": ward.ward_district,
        "deceased_municipality": ward.ward_municipality,
        "deceased_ward_number": ward.ward_no,
        "deceased_tole": tole or "",
        "ward_nepali_province": ward.ward_nepali_province,
        "ward_nepali_district": ward.ward_nepali_district,
        "ward_nepali_municipality": ward.ward_nepali_municipality,
        "ward_nepali_name": ward.ward_nepali_name,
    }

@router.post("/")
def create_death_registration(
    register_ward_id: Optional[UUID] = Form(None),  # kept for backward compat, ignored server-side
    registration_no: Optional[str] = Form(None),
    page_no: Optional[str] = Form(None),
    deceased: str = Form(...),
    death_detail: str = Form(...),
    informant: str = Form(...),
    address: str = Form(...),
    deceased_citizenship_front: Optional[UploadFile] = File(None),
    deceased_citizenship_back: Optional[UploadFile] = File(None),
    informant_citizenship_front: Optional[UploadFile] = File(None),
    informant_citizenship_back: Optional[UploadFile] = File(None),
    hospital_death_report: Optional[UploadFile] = File(None),
    police_report: Optional[UploadFile] = File(None),
    db=Depends(get_db),
    current_user=Depends(require_permission("read_user")),
):
    try:
        try:
            deceased_data = DeceasedRequest.model_validate(json.loads(deceased))
            death_detail_data = DeathDetailRequest.model_validate(json.loads(death_detail))
            informant_data = InformantRequest.model_validate(json.loads(informant))
            address_data = DeathAddressRequest.model_validate(json.loads(address))
        except (json.JSONDecodeError, ValidationError) as e:
            raise HTTPException(status_code=422, detail=f"Invalid JSON in form field: {e}")

        # ── Deceased's permanent address / ward — ENTIRELY server-side ──
        # Same reasoning as birth registration: no legitimate case for a
        # citizen submitting a death registration under a ward other than
        # their own account's ward, so register_ward_id and every
        # deceased_* / ward_nepali_* field are derived from
        # current_user.user_ward_id, not from the client. death_place_*
        # and informant_* are NOT touched here — those stay exactly as
        # the client submitted them.
        ward = _get_user_ward_or_404(db, current_user)
        deceased_tole = (address_data.deceased_tole or "").strip()

        user = db.query(UserModel).filter(UserModel.user_id == current_user.user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        registration = DeathRegistrationModel(
            register_ward_id=ward.ward_id,
            register_submitted_by=current_user.user_id,
            register_status=DeathRegistrationStatus.SUBMITTED,
            registration_no=registration_no,
            page_no=page_no,
        )
        db.add(registration)
        db.flush()

        db.add(DeceasedModel(registration_id=registration.registration_id, **deceased_data.model_dump()))
        db.add(DeathDetailModel(registration_id=registration.registration_id, **death_detail_data.model_dump()))
        db.add(InformantModel(registration_id=registration.registration_id, **informant_data.model_dump()))

        address_obj = DeathAddressModel(
            registration_id=registration.registration_id,
            **_deceased_address_from_ward(ward, tole=deceased_tole),
            death_place_province=address_data.death_place_province,
            death_place_district=address_data.death_place_district,
            death_place_municipality=address_data.death_place_municipality,
            death_place_ward_number=address_data.death_place_ward_number,
            death_place_tole=address_data.death_place_tole,
            informant_province=address_data.informant_province,
            informant_district=address_data.informant_district,
            informant_municipality=address_data.informant_municipality,
            informant_ward_number=address_data.informant_ward_number,
            informant_tole=address_data.informant_tole,
        )
        db.add(address_obj)

        # ---- documents, now -> Cloudinary ----
        if deceased_citizenship_front:
            registration.deceased_citizenship_front_path = _save_death_document(
                registration.registration_id, deceased_citizenship_front, "deceased_citizenship_front"
            )
        if deceased_citizenship_back:
            registration.deceased_citizenship_back_path = _save_death_document(
                registration.registration_id, deceased_citizenship_back, "deceased_citizenship_back"
            )
        if informant_citizenship_front:
            registration.informant_citizenship_front_path = _save_death_document(
                registration.registration_id, informant_citizenship_front, "informant_citizenship_front"
            )
        if informant_citizenship_back:
            registration.informant_citizenship_back_path = _save_death_document(
                registration.registration_id, informant_citizenship_back, "informant_citizenship_back"
            )
        if hospital_death_report:
            registration.hospital_death_report_path = _save_death_document(
                registration.registration_id, hospital_death_report, "hospital_death_report"
            )
        if police_report:
            registration.police_report_path = _save_death_document(
                registration.registration_id, police_report, "police_report"
            )

        db.commit()
        db.refresh(registration)

        return JSONResponse(
            status_code=201,
            content={
                "success": True,
                "status_code": 201,
                "message": "Death registration created successfully",
                "data": serialize(registration, DeathRegistrationResponse),
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/all")
def get_all_death_registrations(db=Depends(get_db), current_user=Depends(require_permission("read_user"))):
    try:
        # Only registrations this citizen submitted — not the whole ward.
        registrations = (
            db.query(DeathRegistrationModel)
            .filter(
                DeathRegistrationModel.register_submitted_by == current_user.user_id,
                DeathRegistrationModel.register_status != DeathRegistrationStatus.DRAFT,
            )
            .all()
        )

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "status_code": 200,
                "message": "Death registrations fetched successfully",
                "total": len(registrations),
                "data": [
                    DeathRegistrationResponseAll.model_validate(
                        registration
                    ).model_dump(mode="json")
                    for registration in registrations
                ]
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/my-address")
def get_my_death_registration_address(
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
                **_deceased_address_from_ward(ward),
            },
        },
    )
@router.get("/ward-chairperson/all")
def get_all_ward_chairperson_registrations(
    db=Depends(get_db),
    current_user=Depends(require_permission("read_user"))
):
    try:
        registrations = (
            db.query(DeathRegistrationModel)
            .filter(DeathRegistrationModel.register_ward_id == current_user.user_ward_id)
            .all()
        )
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "status_code": 200,
                "message": "Registrations fetched successfully",
                "total": len(registrations),
                "data": [
                    DeathRegistrationResponseAll.model_validate(r).model_dump(mode="json")
                    for r in registrations
                ],
            },
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/")
def get_all_registrations(
    status: DeathRegistrationStatus = None,
    ward_id: UUID = None,
    db=Depends(get_db)
):
    try:
        query = db.query(DeathRegistrationModel)

        if status:
            query = query.filter(DeathRegistrationModel.register_status == status)
        if ward_id:
            query = query.filter(DeathRegistrationModel.register_ward_id == ward_id)

        registrations = query.all()

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "status_code": 200,
                "message": "Registrations fetched successfully",
                "total": len(registrations),
                "data": [serialize(r, DeathRegistrationResponse) for r in registrations]
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{registration_id}")
def get_registration(registration_id: UUID, db=Depends(get_db)):
    try:
        registration = db.query(DeathRegistrationModel).filter(
            DeathRegistrationModel.registration_id == registration_id
        ).first()

        if not registration:
            raise HTTPException(status_code=404, detail="Registration not found")

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "status_code": 200,
                "message": "Registration fetched successfully",
                "data": serialize(registration, DeathRegistrationResponse)
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{registration_id}")
def update_registration(
    registration_id: UUID,
    request: UpdateDeathRegistrationRequest,
    db=Depends(get_db)
):
    try:
        registration = db.query(DeathRegistrationModel).filter(
            DeathRegistrationModel.registration_id == registration_id
        ).first()
        if not registration:
            raise HTTPException(status_code=404, detail="Registration not found")

        if registration.register_status == DeathRegistrationStatus.APPROVED:
            raise HTTPException(
                status_code=400,
                detail="Approved registrations cannot be edited"
            )

        if request.register_status:
            registration.register_status = request.register_status

        if request.registration_no is not None:
            registration.registration_no = request.registration_no

        if request.page_no is not None:
            registration.page_no = request.page_no

        if request.deceased and registration.deceased:
            deceased_data = request.deceased.model_dump(exclude_unset=True)
            for field, value in deceased_data.items():
                setattr(registration.deceased, field, value)

        if request.death_detail and registration.death_detail:
            death_detail_data = request.death_detail.model_dump(exclude_unset=True)
            for field, value in death_detail_data.items():
                setattr(registration.death_detail, field, value)

        if request.address and registration.address:
            address_data = request.address.model_dump(exclude_unset=True)
            for field, value in address_data.items():
                setattr(registration.address, field, value)

        db.commit()
        db.refresh(registration)

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "status_code": 200,
                "message": "Registration updated successfully",
                "data": serialize(registration, DeathRegistrationResponse)
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{registration_id}")
def delete_registration(registration_id: UUID, db=Depends(get_db)):
    try:
        registration = db.query(DeathRegistrationModel).filter(
            DeathRegistrationModel.registration_id == registration_id
        ).first()
        if not registration:
            raise HTTPException(status_code=404, detail="Registration not found")

        if registration.register_status != DeathRegistrationStatus.DRAFT:
            raise HTTPException(
                status_code=400,
                detail="Only DRAFT registrations can be deleted"
            )

        db.delete(registration)
        db.commit()

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "status_code": 200,
                "message": "Registration deleted successfully",
                "data": None
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# ══════════════════════════════════════════════
# NESTED ROUTES — Informant / Reject / Approve
# ══════════════════════════════════════════════

@router.put("/{registration_id}/informant")
def update_informant(
    registration_id: UUID,
    request: UpdateInformantRequest,
    db=Depends(get_db)
):
    try:
        informant = db.query(InformantModel).filter(
            InformantModel.registration_id == registration_id
        ).first()
        if not informant:
            raise HTTPException(status_code=404, detail="Informant not found")

        for field, value in request.model_dump(exclude_unset=True).items():
            setattr(informant, field, value)

        db.commit()
        db.refresh(informant)

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "status_code": 200,
                "message": "Informant updated successfully",
                "data": serialize(informant, InformantResponse)
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{registration_id}/reject")
def reject_registration(
    registration_id: UUID,
    request: DeathRejectRequest,
    db=Depends(get_db)
):
    try:
        registration = db.query(DeathRegistrationModel).filter(
            DeathRegistrationModel.registration_id == registration_id
        ).first()
        if not registration:
            raise HTTPException(status_code=404, detail="Registration not found")

        if registration.register_status != DeathRegistrationStatus.SUBMITTED:
            raise HTTPException(
                status_code=400,
                detail="Only SUBMITTED registrations can be rejected"
            )

        registration.register_status = DeathRegistrationStatus.REJECTED

        reject = DeathRejectModel(
            registration_id=registration_id,
            reject_text=request.reject_text
        )
        db.add(reject)
        db.commit()
        db.refresh(reject)

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "status_code": 200,
                "message": "Registration rejected successfully",
                "data": serialize(reject, DeathRejectResponse)
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{registration_id}/approve")
def approve_registration(registration_id: UUID, db=Depends(get_db)):
    try:
        registration = db.query(DeathRegistrationModel).filter(
            DeathRegistrationModel.registration_id == registration_id
        ).first()
        if not registration:
            raise HTTPException(status_code=404, detail="Registration not found")

        if registration.register_status != DeathRegistrationStatus.SUBMITTED:
            raise HTTPException(
                status_code=400,
                detail="Only SUBMITTED registrations can be approved"
            )

        registration.register_status = DeathRegistrationStatus.APPROVED
        db.commit()

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "status_code": 200,
                "message": "Registration approved successfully",
                "data": None
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{registration_id}/upload-documents")
def upload_death_documents(
    registration_id: UUID,
    deceased_citizenship_front: Optional[UploadFile] = File(None),
    deceased_citizenship_back: Optional[UploadFile] = File(None),
    informant_citizenship_front: Optional[UploadFile] = File(None),
    informant_citizenship_back: Optional[UploadFile] = File(None),
    hospital_death_report: Optional[UploadFile] = File(None),
    police_report: Optional[UploadFile] = File(None),
    db=Depends(get_db),
):
    registration = db.query(DeathRegistrationModel).filter(
        DeathRegistrationModel.registration_id == registration_id
    ).first()
    if not registration:
        raise HTTPException(status_code=404, detail="Death registration not found")

    if not any([
        deceased_citizenship_front, deceased_citizenship_back,
        informant_citizenship_front, informant_citizenship_back,
        hospital_death_report, police_report,
    ]):
        raise HTTPException(status_code=400, detail="No file provided")

    try:
        if deceased_citizenship_front:
            registration.deceased_citizenship_front_path = _save_death_document(
                registration_id, deceased_citizenship_front, "deceased_citizenship_front"
            )
        if deceased_citizenship_back:
            registration.deceased_citizenship_back_path = _save_death_document(
                registration_id, deceased_citizenship_back, "deceased_citizenship_back"
            )
        if informant_citizenship_front:
            registration.informant_citizenship_front_path = _save_death_document(
                registration_id, informant_citizenship_front, "informant_citizenship_front"
            )
        if informant_citizenship_back:
            registration.informant_citizenship_back_path = _save_death_document(
                registration_id, informant_citizenship_back, "informant_citizenship_back"
            )
        if hospital_death_report:
            registration.hospital_death_report_path = _save_death_document(
                registration_id, hospital_death_report, "hospital_death_report"
            )
        if police_report:
            registration.police_report_path = _save_death_document(
                registration_id, police_report, "police_report"
            )

        db.commit()
        db.refresh(registration)

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "status_code": 200,
                "message": "Death registration documents uploaded successfully",
                "data": DeathRegistrationDocumentsResponse.model_validate(registration).model_dump(mode="json"),
            },
        )

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{registration_id}/issue-certificate")
def issue_death_certificate(
    registration_id: UUID,
    background_tasks: BackgroundTasks,
    db=Depends(get_db),
    current_user=Depends(require_permission("issue_certificate")),
):
    registration = db.query(DeathRegistrationModel).filter(
        DeathRegistrationModel.registration_id == registration_id
    ).first()
    if not registration:
        raise HTTPException(status_code=404, detail="Registration not found")

    if registration.register_status != DeathRegistrationStatus.VERIFIED:
        raise HTTPException(status_code=400, detail="Only VERIFIED registrations can be issued a certificate")

    try:
        certificate = issue_certificate_for_death_registration(registration, db, current_user.user_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    submitted_by = registration.submitted_by_user
    submitted_by_email = getattr(submitted_by, "user_email", None) if submitted_by else None

    if submitted_by_email:
        download_url = f"{BACKEND_BASE_URL}/v1/death-registration/{registration.registration_id}/certificate/download"
        deceased_name = f"{registration.deceased.deceased_first_name} {registration.deceased.deceased_last_name}"
        background_tasks.add_task(
            send_certificate_ready_email,
            submitted_by_email,
            deceased_name,
            certificate.certificate_no,
            download_url,
        )
        logger.info(f"Death certificate email queued for {submitted_by_email}")
    elif not submitted_by:
        logger.warning(
            f"Death certificate {certificate.certificate_no} issued but registration.submitted_by_user "
            f"is missing — no email sent."
        )
    else:
        logger.warning(
            f"Death certificate {certificate.certificate_no} issued but user {submitted_by.user_id} "
            f"has no user_email on file — no email sent."
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


@router.get("/{registration_id}/certificate/download")
def download_death_certificate(registration_id: UUID, db=Depends(get_db)):
    registration = db.query(DeathRegistrationModel).filter(
        DeathRegistrationModel.registration_id == registration_id
    ).first()
    if not registration or not registration.certificate:
        raise HTTPException(status_code=404, detail="Certificate not found")

    return stream_certificate_pdf(
        registration.certificate.pdf_path,
        registration.certificate.certificate_no,
    )


@router.get("/certificate/verify/{cert_id}", response_model=None)
def verify_death_certificate(cert_id: UUID, db=Depends(get_db)):
    certificate = db.query(DeathCertificateModel).filter(DeathCertificateModel.cert_id == cert_id).first()
    if not certificate:
        raise HTTPException(status_code=404, detail="Certificate not found")

    registration = certificate.registration
    deceased = registration.deceased
    pdf_url = f"{BACKEND_BASE_URL}/v1/death-registration/{registration.registration_id}/certificate/download"

    return JSONResponse(
        status_code=200,
        content=VerifyCertificateResponse(
            valid=certificate.is_valid,
            certificate_no=certificate.certificate_no,
            child_full_name=f"{deceased.deceased_first_name} {deceased.deceased_last_name}",
            register_status=registration.register_status.value,
            issued_date=certificate.created_at,
            revoked_reason=certificate.revoked_reason,
            pdf_url=pdf_url,
        ).model_dump(mode="json"),
    )