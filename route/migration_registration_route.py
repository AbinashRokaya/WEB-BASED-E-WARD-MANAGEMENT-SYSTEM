# router/migration_router.py
import json
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
from config import settings
from database.db import get_db
from enums.migration_enum import MigrationRegistrationStatus
from model.migration_registration_model import (
    MigrationAddressModel, MigrationApplicantModel, MigrationCertificateModel,
    MigrationDetailModel, MigrationFamilyMemberModel, MigrationRegistrationModel,
    MigrationRejectModel,
)
from model.user_model import UserModel
from model.ward_model import WardModel
from schema.certificate_schema import CertificateResponse, VerifyCertificateResponse
from schema.migration_schema import (
    ApplicantRequest, MigrationAddressRequest, MigrationDetailRequest,
    FamilyMemberRequest, MigrationRegistrationDocumentsResponse,
    MigrationRegistrationResponse, MigrationRegistrationResponseAll,
    RejectRequest, RejectResponse, UpdateApplicantRequest,
    UpdateFamilyMemberRequest, UpdateMigrationAddressRequest,
    UpdateMigrationRegistrationRequest,
)
from services.migration_certificate_service import issue_certificate_for_migration_registration
from services.notification_service import notify_certificate_issued
from utils.certificate_download import stream_certificate_pdf
import logging

import cloudinary.uploader
import config.cloudinary_config  # noqa: F401  (runs cloudinary.config() on import)

logger = logging.getLogger(__name__)
# BACKEND_BASE_URL now lives in config/settings.py (it was duplicated
# across four routers, which is exactly how such constants drift apart).

router = APIRouter(
    prefix="/v1/migration-registration",
    tags=["migration-registration"]
)


def serialize(obj, schema):
    return schema.from_orm(obj).model_dump(mode="json")


ALLOWED_MIGRATION_DOC_TYPES = {"image/png", "image/jpeg", "image/jpg", "image/webp", "application/pdf"}

# Cloudinary "folder" prefix — mirrors what MIGRATION_UPLOAD_DIR did for
# the local static/ directory.
CLOUDINARY_MIGRATION_FOLDER = "migration_registration"


def _save_migration_document(migration_id: UUID, file: UploadFile, suffix: str) -> str:
    """
    Uploads a migration-registration document to Cloudinary and returns
    the full secure (https) URL. Previously wrote to
    static/migration_registration/{id}/ and returned a path relative to
    the /static mount; the DB column now stores the full URL directly.
    """
    if file.content_type not in ALLOWED_MIGRATION_DOC_TYPES:
        raise HTTPException(status_code=400, detail="Only PNG/JPEG/WEBP/PDF files allowed")

    resource_type = "raw" if file.content_type == "application/pdf" else "image"
    public_id = f"{CLOUDINARY_MIGRATION_FOLDER}/{migration_id}/{suffix}_{uuid_lib.uuid4().hex[:8]}"

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


@router.post("/")
def create_migration_registration(
    applicant: str = Form(...),          # JSON string -> ApplicantRequest
    addresses: str = Form(...),          # JSON string -> List[MigrationAddressRequest]
    migration_detail: str = Form(...),   # JSON string -> MigrationDetailRequest
    family_members: str = Form("[]"),    # JSON string -> List[FamilyMemberRequest]
    enclosure_citizenship_copy: bool = Form(False),
    enclosure_address_proof: bool = Form(False),
    enclosure_destination_proof: bool = Form(False),
    enclosure_photo_count: Optional[int] = Form(0),
    enclosure_other: Optional[str] = Form(None),
    applicant_citizenship_front: Optional[UploadFile] = File(None),
    applicant_citizenship_back: Optional[UploadFile] = File(None),
    address_proof: Optional[UploadFile] = File(None),
    destination_proof: Optional[UploadFile] = File(None),
    applicant_photo: Optional[UploadFile] = File(None),
    db=Depends(get_db),
    current_user=Depends(require_permission("read_user")),
):
    try:
        try:
            applicant_data = ApplicantRequest.model_validate(json.loads(applicant))
            addresses_data = [MigrationAddressRequest.model_validate(a) for a in json.loads(addresses)]
            migration_detail_data = MigrationDetailRequest.model_validate(json.loads(migration_detail))
            family_members_data = [FamilyMemberRequest.model_validate(m) for m in json.loads(family_members)]
        except (json.JSONDecodeError, ValidationError) as e:
            raise HTTPException(status_code=422, detail=f"Invalid JSON in form field: {e}")

        address_types = {a.address_type for a in addresses_data}
        required_types = {"PERMANENT", "CURRENT", "NEW"}
        if {t.value for t in address_types} != required_types:
            raise HTTPException(
                status_code=422,
                detail="addresses must contain exactly one each of PERMANENT, CURRENT and NEW",
            )

        user = db.query(UserModel).filter(UserModel.user_id == current_user.user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        if not user.ward_id:
            raise HTTPException(
                status_code=400,
                detail="Your account is not assigned to a ward"
            )

        # Ward comes from the authenticated user's own record (UserModel.ward_id),
        # not the request — same trust boundary as birth/death registration.
        ward = db.query(WardModel).filter(WardModel.ward_id == user.ward_id).first()
        if not ward:
            raise HTTPException(status_code=404, detail="Ward not found")

        registration = MigrationRegistrationModel(
            register_ward_id=user.ward_id,
            register_submitted_by=current_user.user_id,
            register_status=MigrationRegistrationStatus.SUBMITTED,
            enclosure_citizenship_copy=enclosure_citizenship_copy,
            enclosure_address_proof=enclosure_address_proof,
            enclosure_destination_proof=enclosure_destination_proof,
            enclosure_photo_count=enclosure_photo_count,
            enclosure_other=enclosure_other,
        )
        db.add(registration)
        db.flush()  # assigns migration_id before commit so documents/rows can reference it

        db.add(MigrationApplicantModel(migration_id=registration.migration_id, **applicant_data.model_dump()))

        for address_data in addresses_data:
            db.add(MigrationAddressModel(migration_id=registration.migration_id, **address_data.model_dump()))

        db.add(MigrationDetailModel(migration_id=registration.migration_id, **migration_detail_data.model_dump()))

        for member_data in family_members_data:
            db.add(MigrationFamilyMemberModel(migration_id=registration.migration_id, **member_data.model_dump()))

        # ---- documents, uploaded in the same request (now -> Cloudinary) ----
        if applicant_citizenship_front:
            registration.applicant_citizenship_front_path = _save_migration_document(
                registration.migration_id, applicant_citizenship_front, "applicant_citizenship_front"
            )
        if applicant_citizenship_back:
            registration.applicant_citizenship_back_path = _save_migration_document(
                registration.migration_id, applicant_citizenship_back, "applicant_citizenship_back"
            )
        if address_proof:
            registration.address_proof_path = _save_migration_document(
                registration.migration_id, address_proof, "address_proof"
            )
        if destination_proof:
            registration.destination_proof_path = _save_migration_document(
                registration.migration_id, destination_proof, "destination_proof"
            )
        if applicant_photo:
            registration.applicant_photo_path = _save_migration_document(
                registration.migration_id, applicant_photo, "applicant_photo"
            )

        db.commit()
        db.refresh(registration)

        return JSONResponse(
            status_code=201,
            content={
                "success": True,
                "status_code": 201,
                "message": "Migration registration created successfully",
                "data": serialize(registration, MigrationRegistrationResponse)
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/all")
def get_all_ward_migration_registrations(
    db=Depends(get_db),
    current_user=Depends(require_permission("read_user"))
):
    try:
        registrations = (
            db.query(MigrationRegistrationModel)
            .filter(
                MigrationRegistrationModel.register_submitted_by == current_user.user_id,
                MigrationRegistrationModel.register_status != MigrationRegistrationStatus.DRAFT,
            )
            .all()
        )

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "status_code": 200,
                "message": "Migration registrations fetched successfully",
                "total": len(registrations),
                "data": [
                    MigrationRegistrationResponseAll.model_validate(r).model_dump(mode="json")
                    for r in registrations
                ]
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/")
def get_all_registrations(
    status: MigrationRegistrationStatus = None,
    ward_id: UUID = None,
    db=Depends(get_db)
):
    try:
        query = db.query(MigrationRegistrationModel)

        if status:
            query = query.filter(MigrationRegistrationModel.register_status == status)
        if ward_id:
            query = query.filter(MigrationRegistrationModel.register_ward_id == ward_id)

        registrations = query.all()

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "status_code": 200,
                "message": "Registrations fetched successfully",
                "total": len(registrations),
                "data": [serialize(r, MigrationRegistrationResponse) for r in registrations]
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{migration_id}")
def get_registration(migration_id: UUID, db=Depends(get_db)):
    try:
        registration = db.query(MigrationRegistrationModel).filter(
            MigrationRegistrationModel.migration_id == migration_id
        ).first()

        if not registration:
            raise HTTPException(status_code=404, detail="Registration not found")

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "status_code": 200,
                "message": "Registration fetched successfully",
                "data": serialize(registration, MigrationRegistrationResponse)
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{migration_id}")
def update_registration(
    migration_id: UUID,
    request: UpdateMigrationRegistrationRequest,
    db=Depends(get_db)
):
    try:
        registration = db.query(MigrationRegistrationModel).filter(
            MigrationRegistrationModel.migration_id == migration_id
        ).first()
        if not registration:
            raise HTTPException(status_code=404, detail="Registration not found")

        if registration.register_status == MigrationRegistrationStatus.APPROVED:
            raise HTTPException(
                status_code=400,
                detail="Approved registrations cannot be edited"
            )

        if request.register_status:
            registration.register_status = request.register_status

        for field in (
            "enclosure_citizenship_copy", "enclosure_address_proof",
            "enclosure_destination_proof", "enclosure_photo_count", "enclosure_other",
            "applicant_citizenship_front_path", "applicant_citizenship_back_path",
            "address_proof_path", "destination_proof_path", "applicant_photo_path",
        ):
            value = getattr(request, field)
            if value is not None:
                setattr(registration, field, value)

        if request.applicant and registration.applicant:
            applicant_data = request.applicant.model_dump(exclude_unset=True)
            for field, value in applicant_data.items():
                setattr(registration.applicant, field, value)

        if request.migration_detail and registration.migration_detail:
            detail_data = request.migration_detail.model_dump(exclude_unset=True)
            for field, value in detail_data.items():
                setattr(registration.migration_detail, field, value)

        db.commit()
        db.refresh(registration)

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "status_code": 200,
                "message": "Registration updated successfully",
                "data": serialize(registration, MigrationRegistrationResponse)
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{migration_id}")
def delete_registration(migration_id: UUID, db=Depends(get_db)):
    try:
        registration = db.query(MigrationRegistrationModel).filter(
            MigrationRegistrationModel.migration_id == migration_id
        ).first()
        if not registration:
            raise HTTPException(status_code=404, detail="Registration not found")

        if registration.register_status != MigrationRegistrationStatus.DRAFT:
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
# NESTED ROUTES — Address / Family Member / Reject
# ══════════════════════════════════════════════

@router.put("/{migration_id}/addresses/{address_id}")
def update_address(
    migration_id: UUID,
    address_id: UUID,
    request: UpdateMigrationAddressRequest,
    db=Depends(get_db)
):
    try:
        address = db.query(MigrationAddressModel).filter(
            MigrationAddressModel.address_id == address_id,
            MigrationAddressModel.migration_id == migration_id
        ).first()
        if not address:
            raise HTTPException(status_code=404, detail="Address not found")

        for field, value in request.model_dump(exclude_unset=True).items():
            setattr(address, field, value)

        db.commit()
        db.refresh(address)

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "status_code": 200,
                "message": "Address updated successfully",
                "data": request.model_dump(exclude_unset=True)
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{migration_id}/family-members/{family_member_id}")
def update_family_member(
    migration_id: UUID,
    family_member_id: UUID,
    request: UpdateFamilyMemberRequest,
    db=Depends(get_db)
):
    try:
        member = db.query(MigrationFamilyMemberModel).filter(
            MigrationFamilyMemberModel.family_member_id == family_member_id,
            MigrationFamilyMemberModel.migration_id == migration_id
        ).first()
        if not member:
            raise HTTPException(status_code=404, detail="Family member not found")

        for field, value in request.model_dump(exclude_unset=True).items():
            setattr(member, field, value)

        db.commit()
        db.refresh(member)

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "status_code": 200,
                "message": "Family member updated successfully",
                "data": request.model_dump(exclude_unset=True)
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{migration_id}/reject")
def reject_registration(
    migration_id: UUID,
    request: RejectRequest,
    db=Depends(get_db)
):
    try:
        registration = db.query(MigrationRegistrationModel).filter(
            MigrationRegistrationModel.migration_id == migration_id
        ).first()
        if not registration:
            raise HTTPException(status_code=404, detail="Registration not found")

        if registration.register_status != MigrationRegistrationStatus.SUBMITTED:
            raise HTTPException(
                status_code=400,
                detail="Only SUBMITTED registrations can be rejected"
            )

        registration.register_status = MigrationRegistrationStatus.REJECTED

        reject = MigrationRejectModel(
            migration_id=migration_id,
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
                "data": serialize(reject, RejectResponse)
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{migration_id}/approve")
def approve_registration(
    migration_id: UUID,
    db=Depends(get_db),
    current_user=Depends(require_permission("update_user")),   # was: no auth at all
):
    try:
        registration = db.query(MigrationRegistrationModel).filter(
            MigrationRegistrationModel.migration_id == migration_id
        ).first()
        if not registration:
            raise HTTPException(status_code=404, detail="Registration not found")

        if registration.register_status != MigrationRegistrationStatus.SUBMITTED:
            raise HTTPException(
                status_code=400,
                detail="Only SUBMITTED registrations can be approved"
            )

        registration.register_status = MigrationRegistrationStatus.APPROVED
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


@router.post("/{migration_id}/upload-documents")
def upload_migration_documents(
    migration_id: UUID,
    applicant_citizenship_front: Optional[UploadFile] = File(None),
    applicant_citizenship_back: Optional[UploadFile] = File(None),
    address_proof: Optional[UploadFile] = File(None),
    destination_proof: Optional[UploadFile] = File(None),
    applicant_photo: Optional[UploadFile] = File(None),
    db=Depends(get_db),
):
    registration = db.query(MigrationRegistrationModel).filter(
        MigrationRegistrationModel.migration_id == migration_id
    ).first()
    if not registration:
        raise HTTPException(status_code=404, detail="Migration registration not found")

    if not any([
        applicant_citizenship_front, applicant_citizenship_back,
        address_proof, destination_proof, applicant_photo,
    ]):
        raise HTTPException(status_code=400, detail="No file provided")

    try:
        if applicant_citizenship_front:
            registration.applicant_citizenship_front_path = _save_migration_document(
                migration_id, applicant_citizenship_front, "applicant_citizenship_front"
            )
        if applicant_citizenship_back:
            registration.applicant_citizenship_back_path = _save_migration_document(
                migration_id, applicant_citizenship_back, "applicant_citizenship_back"
            )
        if address_proof:
            registration.address_proof_path = _save_migration_document(
                migration_id, address_proof, "address_proof"
            )
        if destination_proof:
            registration.destination_proof_path = _save_migration_document(
                migration_id, destination_proof, "destination_proof"
            )
        if applicant_photo:
            registration.applicant_photo_path = _save_migration_document(
                migration_id, applicant_photo, "applicant_photo"
            )

        db.commit()
        db.refresh(registration)

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "status_code": 200,
                "message": "Migration registration documents uploaded successfully",
                "data": MigrationRegistrationDocumentsResponse.model_validate(registration).model_dump(mode="json"),
            },
        )

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{migration_id}/issue-certificate")
def issue_migration_certificate(
    migration_id: UUID,
    background_tasks: BackgroundTasks,
    db=Depends(get_db),
    current_user=Depends(require_permission("issue_certificate")),
):
    registration = db.query(MigrationRegistrationModel).filter(
        MigrationRegistrationModel.migration_id == migration_id
    ).first()
    if not registration:
        raise HTTPException(status_code=404, detail="Registration not found")

    if registration.register_status != MigrationRegistrationStatus.VERIFIED:
        raise HTTPException(status_code=400, detail="Only VERIFIED registrations can be issued a certificate")

    try:
        certificate = issue_certificate_for_migration_registration(registration, db, current_user.user_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Was ~20 lines of duplicated recipient lookup + three log branches.
    emailed = notify_certificate_issued(background_tasks, "migration", registration, certificate)

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


@router.get("/{migration_id}/certificate/download")
def download_migration_certificate(migration_id: UUID, db=Depends(get_db)):
    registration = db.query(MigrationRegistrationModel).filter(
        MigrationRegistrationModel.migration_id == migration_id
    ).first()
    if not registration or not registration.certificate:
        raise HTTPException(status_code=404, detail="Certificate not found")

    return stream_certificate_pdf(
        registration.certificate.pdf_path,
        registration.certificate.certificate_no,
    )


@router.get("/certificate/verify/{cert_id}", response_model=None)
def verify_migration_certificate(cert_id: UUID, db=Depends(get_db)):
    certificate = db.query(MigrationCertificateModel).filter(MigrationCertificateModel.cert_id == cert_id).first()
    if not certificate:
        raise HTTPException(status_code=404, detail="Certificate not found")

    registration = certificate.registration
    applicant = registration.applicant
    pdf_url = f"{settings.BACKEND_BASE_URL}/v1/migration-registration/{registration.migration_id}/certificate/download"

    return JSONResponse(
        status_code=200,
        content=VerifyCertificateResponse(
            valid=certificate.is_valid,
            certificate_no=certificate.certificate_no,
            child_full_name=applicant.applicant_full_name_en,
            register_status=registration.register_status.value,
            issued_date=certificate.created_at,
            revoked_reason=certificate.revoked_reason,
            pdf_url=pdf_url,
        ).model_dump(mode="json"),
    )