import os
import logging

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
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
from services.email_service import send_certificate_ready_email
from auth.current_user import require_permission

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/birth-registration", tags=["certificate"])

# Public base URL of THIS backend (where the download route below actually
# lives). Deliberately separate from services.certificate_service.VERIFY_BASE_URL,
# which points at the frontend's /verify page that the QR code links to —
# those are two different servers/ports and should not be derived from
# each other.
BACKEND_BASE_URL = os.environ.get("BACKEND_BASE_URL", "http://localhost:8000")


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

    # Previously this block failed completely silently if submitted_by was
    # missing or had no email — no log line, nothing. That made it look
    # like the SMTP config itself was broken when the real issue was
    # upstream: the email was never even queued as a background task.
    submitted_by = registration.submitted_by_user
    submitted_by_email = getattr(submitted_by, "user_email", None) if submitted_by else None

    if submitted_by_email:
        download_url = f"{BACKEND_BASE_URL}/v1/birth-registration/{registration.registration_id}/certificate/download"
        background_tasks.add_task(
            send_certificate_ready_email,
            submitted_by_email,
            f"{registration.child.child_first_name} {registration.child.child_last_name}",
            certificate.certificate_no,
            download_url,
        )
        logger.info(f"Certificate email queued for {submitted_by_email}")
    elif not submitted_by:
        logger.warning(
            f"Certificate {certificate.certificate_no} issued but registration.submitted_by_user "
            f"is missing — no email sent."
        )
    else:
        logger.warning(
            f"Certificate {certificate.certificate_no} issued but user {submitted_by.user_id} "
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
def download_certificate(registration_id: UUID, db=Depends(get_db)):
    registration = db.query(BirthRegistrationModel).filter(
        BirthRegistrationModel.registration_id == registration_id
    ).first()
    if not registration or not registration.certificate:
        raise HTTPException(status_code=404, detail="Certificate not found")

    pdf_path = os.path.join("static", registration.certificate.pdf_path)
    if not os.path.exists(pdf_path):
        raise HTTPException(status_code=404, detail="Certificate file missing on server")

    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        headers={
            # "inline" tells the browser to render it (e.g. in an <iframe>)
            # instead of forcing a download.
            "Content-Disposition": f'inline; filename="{registration.certificate.certificate_no}.pdf"'
        },
    )


# Public — no auth. This is what the QR code links to.
@router.get("/certificate/verify/{cert_id}", response_model=None)
def verify_certificate(cert_id: UUID, db=Depends(get_db)):
    certificate = db.query(CertificateModel).filter(CertificateModel.cert_id == cert_id).first()
    if not certificate:
        raise HTTPException(status_code=404, detail="Certificate not found")

    registration = certificate.registration
    child = registration.child

    return JSONResponse(
        status_code=200,
        content=VerifyCertificateResponse(
            valid=certificate.is_valid,
            certificate_no=certificate.certificate_no,
            child_full_name=f"{child.child_first_name} {child.child_last_name}",
            register_status=registration.register_status.value,
            issued_date=certificate.created_at,
            revoked_reason=certificate.revoked_reason,
        ).model_dump(mode="json"),
    )