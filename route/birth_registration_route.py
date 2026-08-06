# router/birth_registration_router.py
from fastapi import HTTPException, APIRouter, Depends, UploadFile, File, Form
from fastapi.responses import JSONResponse
from uuid import UUID
from database.db import get_db
from model.birth_registration_model import (
    BirthRegistrationModel, ChildModel, ParentModel,
    NomineeModel, AddressModel, RejectModel
)
from model.ward_model import WardModel
from model.user_model import UserModel
from model.enums import BirthRegistrationStatus
from schema.birth_registration_schema import (
    BirthRegistrationRequest, BirthRegistrationResponse,
    UpdateRegistrationRequest, RejectRequest, RejectResponse,
    UpdateParentRequest, ParentResponse, UpdateNomineeRequest,
    UpdateAddressRequest, AddressResponse, BirthRegistrationResponseAll,
    ChildRequest, ParentRequest, NomineeRequest, AddressRequest,
)
import os
import uuid as uuid_lib
from typing import Optional
from auth.current_user import require_permission
import json
from pydantic import ValidationError

import cloudinary.uploader
import config.cloudinary_config  # noqa: F401  (runs cloudinary.config() on import)

router = APIRouter(
    prefix="/v1/birth-registration",
    tags=["birth-registration"]
)


def serialize(obj, schema):
    return schema.from_orm(obj).model_dump(mode="json")


ALLOWED_DOC_TYPES = {"image/png", "image/jpeg", "image/jpg", "image/webp", "application/pdf"}

# Cloudinary "folder" prefix for this app's uploads — keeps birth-registration
# documents grouped together in the Cloudinary media library, analogous to
# what BIRTH_UPLOAD_DIR did for the local static/ directory.
CLOUDINARY_BIRTH_FOLDER = "birth_registration"


def _get_user_ward_or_404(db, current_user) -> WardModel:
    """Look up the logged-in citizen's own ward — single source of truth
    for 'my own ward' in this router, same as recommendation_router.py."""
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


def _birth_address_from_ward(ward: WardModel, tole: str = "") -> dict:
    """Builds the AddressModel field dict entirely from a WardModel row —
    the stored address always reflects real ward data, never client input
    (except tole, which is genuinely just free text)."""
    return {
        "child_province": ward.ward_province,
        "child_district": ward.ward_district,
        "child_municipality": ward.ward_municipality,
        "child_ward_number": ward.ward_no,
        "child_tole": tole or "",
        "ward_nepali_province": ward.ward_nepali_province,
        "ward_nepali_district": ward.ward_nepali_district,
        "ward_nepali_municipality": ward.ward_nepali_municipality,
        "ward_nepali_name": ward.ward_nepali_name,
        "ward_type": ward.ward_type,
    }


def _save_birth_document(registration_id: UUID, file: UploadFile, suffix: str) -> str:
    """
    Uploads a birth-registration document to Cloudinary and returns the
    full secure (https) URL. Previously wrote to
    static/birth_registration/{id}/ and returned a path relative to the
    /static mount; the DB column now stores the full URL directly.
    """
    if file.content_type not in ALLOWED_DOC_TYPES:
        raise HTTPException(status_code=400, detail="Only PNG/JPEG/WEBP/PDF files allowed")

    resource_type = "raw" if file.content_type == "application/pdf" else "image"
    public_id = f"{CLOUDINARY_BIRTH_FOLDER}/{registration_id}/{suffix}_{uuid_lib.uuid4().hex[:8]}"

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
def create_birth_registration(
    register_ward_id: Optional[UUID] = Form(None),  # kept for backward compat, ignored server-side
    child: str = Form(...),
    parents: str = Form(...),
    nominees: str = Form("[]"),
    address: str = Form(...),
    father_citizenship_front: Optional[UploadFile] = File(None),
    father_citizenship_back: Optional[UploadFile] = File(None),
    mother_citizenship_front: Optional[UploadFile] = File(None),
    mother_citizenship_back: Optional[UploadFile] = File(None),
    hospital_birth_certificate: Optional[UploadFile] = File(None),
    vaccination_card: Optional[UploadFile] = File(None),
    db=Depends(get_db),
    current_user=Depends(require_permission("read_user")),
):
    try:
        try:
            child_data = ChildRequest.model_validate(json.loads(child))
            parents_data = [ParentRequest.model_validate(p) for p in json.loads(parents)]
            nominees_data = [NomineeRequest.model_validate(n) for n in json.loads(nominees)]
            address_data = AddressRequest.model_validate(json.loads(address))
        except (json.JSONDecodeError, ValidationError) as e:
            raise HTTPException(status_code=422, detail=f"Invalid JSON in form field: {e}")

        # ── Ward / address resolution — ENTIRELY server-side ───────────
        # Unlike recommendation letters, birth registration has no
        # legitimate case for registering under a ward other than the
        # citizen's own, so we always derive the ward (and every address
        # field except tole) from current_user.user_ward_id — the same
        # ward GET /my-address returns. Whatever register_ward_id/address
        # the client submits is display-only and is never trusted here.
        ward = _get_user_ward_or_404(db, current_user)
        tole = (address_data.child_tole or "").strip()

        user = db.query(UserModel).filter(UserModel.user_id == current_user.user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        if len(parents_data) < 1:
            raise HTTPException(status_code=400, detail="At least one parent is required")

        registration = BirthRegistrationModel(
            register_ward_id=ward.ward_id,
            register_submitted_by=current_user.user_id,
            register_status=BirthRegistrationStatus.SUBMITTED,
        )
        db.add(registration)
        db.flush()

        child_obj = ChildModel(
            registration_id=registration.registration_id,
            **child_data.model_dump(),
        )
        db.add(child_obj)

        for parent_data in parents_data:
            db.add(ParentModel(
                registration_id=registration.registration_id,
                **parent_data.model_dump(),
            ))

        for nominee_data in nominees_data:
            db.add(NomineeModel(
                nominee_registration_id=registration.registration_id,
                **nominee_data.model_dump(),
            ))

        address_obj = AddressModel(
            registration_id=registration.registration_id,
            **_birth_address_from_ward(ward, tole=tole),
        )
        db.add(address_obj)

        # ---- documents, uploaded in the same request (now -> Cloudinary) ----
        if father_citizenship_front:
            registration.father_citizenship_front_path = _save_birth_document(
                registration.registration_id, father_citizenship_front, "father_citizenship_front"
            )
        if father_citizenship_back:
            registration.father_citizenship_back_path = _save_birth_document(
                registration.registration_id, father_citizenship_back, "father_citizenship_back"
            )
        if mother_citizenship_front:
            registration.mother_citizenship_front_path = _save_birth_document(
                registration.registration_id, mother_citizenship_front, "mother_citizenship_front"
            )
        if mother_citizenship_back:
            registration.mother_citizenship_back_path = _save_birth_document(
                registration.registration_id, mother_citizenship_back, "mother_citizenship_back"
            )
        if hospital_birth_certificate:
            registration.hospital_birth_certificate_path = _save_birth_document(
                registration.registration_id, hospital_birth_certificate, "hospital_certificate"
            )
        if vaccination_card:
            registration.vaccination_card_path = _save_birth_document(
                registration.registration_id, vaccination_card, "vaccination_card"
            )

        db.commit()
        db.refresh(registration)

        return JSONResponse(
            status_code=201,
            content={
                "success": True,
                "status_code": 201,
                "message": "Birth registration created successfully",
                "data": serialize(registration, BirthRegistrationResponse),
            },
        )

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    

@router.get("/")
def get_all_registrations(
    status: BirthRegistrationStatus = None,
    ward_id: UUID = None,
    db=Depends(get_db)
):
    try:
        query = db.query(BirthRegistrationModel)

        if status:
            query = query.filter(BirthRegistrationModel.register_status == status)
        if ward_id:
            query = query.filter(BirthRegistrationModel.register_ward_id == ward_id)

        registrations = query.all()

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "status_code": 200,
                "message": "Registrations fetched successfully",
                "total": len(registrations),
                "data": [serialize(r, BirthRegistrationResponse) for r in registrations]
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/my-address")
def get_my_birth_registration_address(
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
                **_birth_address_from_ward(ward),
            },
        },
    )
@router.get("/{registration_id}")
def get_registration(registration_id: UUID, db=Depends(get_db)):
    try:
        registration = db.query(BirthRegistrationModel).filter(
            BirthRegistrationModel.registration_id == registration_id
        ).first()

        if not registration:
            raise HTTPException(status_code=404, detail="Registration not found")

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "status_code": 200,
                "message": "Registration fetched successfully",
                "data": serialize(registration, BirthRegistrationResponse)
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{registration_id}")
def update_registration(
    registration_id: UUID,
    request: UpdateRegistrationRequest,
    db=Depends(get_db)
):
    try:
        registration = db.query(BirthRegistrationModel).filter(
            BirthRegistrationModel.registration_id == registration_id
        ).first()
        if not registration:
            raise HTTPException(status_code=404, detail="Registration not found")

        if registration.register_status == BirthRegistrationStatus.APPROVED:
            raise HTTPException(
                status_code=400,
                detail="Approved registrations cannot be edited"
            )

        if request.register_status:
            registration.register_status = request.register_status

        if request.child and registration.child:
            child_data = request.child.model_dump(exclude_unset=True)
            for field, value in child_data.items():
                setattr(registration.child, field, value)

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
                "data": serialize(registration, BirthRegistrationResponse)
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
        registration = db.query(BirthRegistrationModel).filter(
            BirthRegistrationModel.registration_id == registration_id
        ).first()
        if not registration:
            raise HTTPException(status_code=404, detail="Registration not found")

        if registration.register_status != BirthRegistrationStatus.DRAFT:
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
# NESTED ROUTES — Parent / Nominee / Reject
# ══════════════════════════════════════════════

@router.put("/{registration_id}/parents/{parent_id}")
def update_parent(
    registration_id: UUID,
    parent_id: UUID,
    request: UpdateParentRequest,
    db=Depends(get_db)
):
    try:
        parent = db.query(ParentModel).filter(
            ParentModel.parent_id == parent_id,
            ParentModel.registration_id == registration_id
        ).first()
        if not parent:
            raise HTTPException(status_code=404, detail="Parent not found")

        for field, value in request.model_dump(exclude_unset=True).items():
            setattr(parent, field, value)

        db.commit()
        db.refresh(parent)

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "status_code": 200,
                "message": "Parent updated successfully",
                "data": serialize(parent, ParentResponse)
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{registration_id}/nominees/{nominee_id}")
def update_nominee(
    registration_id: UUID,
    nominee_id: UUID,
    request: UpdateNomineeRequest,
    db=Depends(get_db)
):
    try:
        nominee = db.query(NomineeModel).filter(
            NomineeModel.nominee_id == nominee_id,
            NomineeModel.nominee_registration_id == registration_id
        ).first()
        if not nominee:
            raise HTTPException(status_code=404, detail="Nominee not found")

        for field, value in request.model_dump(exclude_unset=True).items():
            setattr(nominee, field, value)

        db.commit()
        db.refresh(nominee)

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "status_code": 200,
                "message": "Nominee updated successfully",
                "data": request.model_dump(exclude_unset=True)
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
    request: RejectRequest,
    db=Depends(get_db)
):
    try:
        registration = db.query(BirthRegistrationModel).filter(
            BirthRegistrationModel.registration_id == registration_id
        ).first()
        if not registration:
            raise HTTPException(status_code=404, detail="Registration not found")

        if registration.register_status != BirthRegistrationStatus.SUBMITTED:
            raise HTTPException(
                status_code=400,
                detail="Only SUBMITTED registrations can be rejected"
            )

        registration.register_status = BirthRegistrationStatus.REJECTED

        reject = RejectModel(
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
                "data": serialize(reject, RejectResponse)
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
        registration = db.query(BirthRegistrationModel).filter(
            BirthRegistrationModel.registration_id == registration_id
        ).first()
        if not registration:
            raise HTTPException(status_code=404, detail="Registration not found")

        if registration.register_status != BirthRegistrationStatus.SUBMITTED:
            raise HTTPException(
                status_code=400,
                detail="Only SUBMITTED registrations can be approved"
            )

        registration.register_status = BirthRegistrationStatus.APPROVED
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
def upload_birth_documents(
    registration_id: UUID,
    father_citizenship_front: Optional[UploadFile] = File(None),
    father_citizenship_back: Optional[UploadFile] = File(None),
    mother_citizenship_front: Optional[UploadFile] = File(None),
    mother_citizenship_back: Optional[UploadFile] = File(None),
    hospital_birth_certificate: Optional[UploadFile] = File(None),
    vaccination_card: Optional[UploadFile] = File(None),
    db=Depends(get_db),
    current_user=Depends(require_permission("update_registration")),
):
    registration = (
        db.query(BirthRegistrationModel)
        .filter(BirthRegistrationModel.registration_id == registration_id)
        .first()
    )
    if not registration:
        raise HTTPException(status_code=404, detail="Birth registration not found")

    if not any([
        father_citizenship_front, father_citizenship_back,
        mother_citizenship_front, mother_citizenship_back,
        hospital_birth_certificate, vaccination_card,
    ]):
        raise HTTPException(status_code=400, detail="No file provided")

    try:
        if father_citizenship_front:
            registration.father_citizenship_front_path = _save_birth_document(
                registration_id, father_citizenship_front, "father_citizenship_front"
            )
        if father_citizenship_back:
            registration.father_citizenship_back_path = _save_birth_document(
                registration_id, father_citizenship_back, "father_citizenship_back"
            )
        if mother_citizenship_front:
            registration.mother_citizenship_front_path = _save_birth_document(
                registration_id, mother_citizenship_front, "mother_citizenship_front"
            )
        if mother_citizenship_back:
            registration.mother_citizenship_back_path = _save_birth_document(
                registration_id, mother_citizenship_back, "mother_citizenship_back"
            )
        if hospital_birth_certificate:
            registration.hospital_birth_certificate_path = _save_birth_document(
                registration_id, hospital_birth_certificate, "hospital_certificate"
            )
        if vaccination_card:
            registration.vaccination_card_path = _save_birth_document(
                registration_id, vaccination_card, "vaccination_card"
            )

        db.commit()
        db.refresh(registration)

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "status_code": 200,
                "message": "Birth registration documents uploaded successfully",
                "data": {
                    "father_citizenship_front_path": registration.father_citizenship_front_path,
                    "father_citizenship_back_path": registration.father_citizenship_back_path,
                    "mother_citizenship_front_path": registration.mother_citizenship_front_path,
                    "mother_citizenship_back_path": registration.mother_citizenship_back_path,
                    "hospital_birth_certificate_path": registration.hospital_birth_certificate_path,
                    "vaccination_card_path": registration.vaccination_card_path,
                },
            },
        )

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))