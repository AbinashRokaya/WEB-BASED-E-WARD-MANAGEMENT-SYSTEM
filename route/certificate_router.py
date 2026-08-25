import logging

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from fastapi.responses import JSONResponse
from uuid import UUID

from database.db import get_db
from model.birth_registration_model import BirthRegistrationModel, CertificateModel
from model.enums import BirthRegistrationStatus
from schema.certificate_schema import CertificateResponse, VerifyCertificateResponse
from services.certificate_service import (
    generate_certificate_no,
    compute_data_hash,
    generate_qr,
    render_certificate_pdf,
    issue_certificate_for_registration,
)
from utils.certificate_download import stream_certificate_pdf
from services.notification_service import notify_certificate_issued
from auth.current_user import require_permission
from config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/birth-registration", tags=["certificate"])

# Base URLs now come from config/settings.py — they were duplicated
# across four routers, which is how they drift apart.


@router.post("/{registration_id}/issue-certificate")
def issue_certificate(
    registration_id: UUID,
    background_tasks: BackgroundTasks,
    db=Depends(get_db),
    current_user=Depends(require_permission("issue_certificate")),
):
    registration = db.query(BirthRegistrationModel).filter(
        BirthRegistrationModel.registration_id == registration_id
    ).first()
    if not registration:
        raise HTTPException(status_code=404, detail="Registration not found")

    if registration.register_status != BirthRegistrationStatus.VERIFIED:
        raise HTTPException(status_code=400, detail="Only VERIFIED registrations can be issued a certificate")

    try:
        certificate = issue_certificate_for_registration(registration, db, current_user.user_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # All of this used to be ~20 lines duplicated in four routers, each with
    # slightly different logging. It now lives in notification_service.
    emailed = notify_certificate_issued(background_tasks, "birth", registration, certificate)

    return JSONResponse(
        status_code=201,
        content={
            "success": True,
            "status_code": 201,
            "message": "Certificate issued successfully",
            "notification_sent": emailed,
            "data": CertificateResponse.model_validate(certificate).model_dump(mode="json"),
        },
    )


@router.get("/{registration_id}/certificate/download")
def download_certificate(registration_id: UUID, db=Depends(get_db)):
    registration = db.query(BirthRegistrationModel).filter(
        BirthRegistrationModel.registration_id == registration_id
    ).first()
    if not registration or not registration.certificate:
        raise HTTPException(status_code=404, detail="Certificate not found")

    return stream_certificate_pdf(
        registration.certificate.pdf_path,
        registration.certificate.certificate_no,
    )

# Public — no auth. This is what the QR code links to.
@router.get("/certificate/verify/{cert_id}", response_model=None)
def verify_certificate(cert_id: UUID, db=Depends(get_db)):
    certificate = db.query(CertificateModel).filter(CertificateModel.cert_id == cert_id).first()
    if not certificate:
        raise HTTPException(status_code=404, detail="Certificate not found")

    registration = certificate.registration
    child = registration.child
    pdf_url = f"{settings.BACKEND_BASE_URL}/v1/birth-registration/{registration.registration_id}/certificate/download"

    return JSONResponse(
        status_code=200,
        content=VerifyCertificateResponse(
            valid=certificate.is_valid,
            certificate_no=certificate.certificate_no,
            child_full_name=f"{child.child_first_name} {child.child_last_name}",
            register_status=registration.register_status.value,
            issued_date=certificate.created_at,
            revoked_reason=certificate.revoked_reason,
            pdf_url=pdf_url,
        ).model_dump(mode="json"),
    )