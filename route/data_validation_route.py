# router/data_validation_router.py
from fastapi import HTTPException, APIRouter, Depends
from fastapi.responses import JSONResponse
from uuid import UUID
from database.db import get_db

# ── Birth ──────────────────────────────────────────────
from model.birth_registration_model import (
    BirthRegistrationModel, ChildModel, ParentModel,
    NomineeModel, AddressModel, RejectModel
)
from model.enums import BirthRegistrationStatus
from schema.birth_registration_schema import (
    BirthRegistrationRequest, BirthRegistrationResponse,
    UpdateRegistrationRequest, RejectRequest, RejectResponse,
    UpdateParentRequest, UpdateNomineeRequest, UpdateAddressRequest,
    AddressResponse, BirthRegistrationResponseAll
)

# ── Death ──────────────────────────────────────────────
from model.death_registration_model import (
    DeathRegistrationModel, DeathRejectModel
)
from enums.death_enum import DeathRegistrationStatus
from schema.death_schema import (
    DeathRejectRequest, DeathRejectResponse, DeathRegistrationResponseAll
)

# ── Migration ────────────────────────────────────────────
from model.migration_registration_model import (
    MigrationRegistrationModel, MigrationRejectModel
)
from enums.migration_enum import MigrationRegistrationStatus
from schema.migration_schema import (
    RejectRequest as MigrationRejectRequest,
    RejectResponse as MigrationRejectResponse,
    MigrationRegistrationResponseAll
)

# ── Complaint ────────────────────────────────────────────
from model.complaint_model import ComplaintModel, ComplaintRejectModel
from enums.complaint_enum import ComplaintStatus
from schema.complaint_schema import (
    ComplaintRejectRequest, ComplaintRejectResponse, ComplaintResponseAll
)

# ── Recommendation ───────────────────────────────────────
from model.recommendation_model import (
    RecommendationLetterModel, RecommendationRejectModel
)
from enums.recommendation_enum import RecommendationStatus
from schema.recommendation_schema import (
    RejectRequest as RecommendationRejectRequest,
    RejectResponse as RecommendationRejectResponse,
    RecommendationLetterResponse,
)

from model.ward_model import WardModel
from model.user_model import UserModel
from auth.current_user import require_permission

router = APIRouter(
    prefix="/v1/data-validation",
    tags=["Data Validation"]
)

# SECURITY FIX: every endpoint below previously used
# require_permission("read_user"). RoleSchema.Citizen ALSO has "read_user",
# so any logged-in citizen could approve or reject any registration in the
# system just by calling these URLs directly. They now require
# "validate_data", which only the DataValidationOfficer (and SuperAdmin) has.


def serialize(obj, schema):
    return schema.from_orm(obj).model_dump(mode="json")


# ══════════════════════════════════════════════
# BIRTH
# ══════════════════════════════════════════════

@router.get("/all")
def get_all_birth_registrations(
    db=Depends(get_db),
    current_user=Depends(require_permission("validate_data")),
):
    try:
        registrations = (
            db.query(BirthRegistrationModel)
            .filter(
                BirthRegistrationModel.register_status == "SUBMITTED",
                BirthRegistrationModel.register_ward_id == current_user.user_ward_id,
            )
            .all()
        )

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "status_code": 200,
                "message": "Birth registrations fetched successfully",
                "total": len(registrations),
                "data": [
                    BirthRegistrationResponseAll.model_validate(
                        registration
                    ).model_dump(mode="json")
                    for registration in registrations
                ]
            }
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{registration_id}/approve")
def approve_registration(
    registration_id: UUID,
    db=Depends(get_db),
    current_user=Depends(require_permission("validate_data")),
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
                detail=f"Only SUBMITTED registrations can be approved (current status: {registration.register_status.value})"
            )

        registration.register_status = BirthRegistrationStatus.APPROVED
        db.commit()

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "status_code": 200,
                "message": "Registration APPROVED successfully",
                "data": None
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
    db=Depends(get_db),
    current_user=Depends(require_permission("validate_data")),
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


# ══════════════════════════════════════════════
# DEATH
# ══════════════════════════════════════════════

@router.get("/death/all")
def get_all_death_registrations(
    db=Depends(get_db),
    current_user=Depends(require_permission("validate_data")),
):
    try:
        registrations = (
            db.query(DeathRegistrationModel)
            .filter(
                DeathRegistrationModel.register_status == "SUBMITTED",
                # NOTE: assuming the ward FK column is named the same as
                # birth's (register_ward_id) — verify against
                # model/death_registration_model.py and adjust if different.
                DeathRegistrationModel.register_ward_id == current_user.user_ward_id,
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

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/death/{registration_id}/approve")
def approve_death_registration(
    registration_id: UUID,
    db=Depends(get_db),
    current_user=Depends(require_permission("validate_data")),
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
                detail=f"Only SUBMITTED registrations can be approved (current status: {registration.register_status.value})"
            )

        registration.register_status = DeathRegistrationStatus.APPROVED
        db.commit()

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "status_code": 200,
                "message": "Registration APPROVED successfully",
                "data": None
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/death/{registration_id}/reject")
def reject_death_registration(
    registration_id: UUID,
    request: DeathRejectRequest,
    db=Depends(get_db),
    current_user=Depends(require_permission("validate_data")),
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


# ══════════════════════════════════════════════
# MIGRATION
# ══════════════════════════════════════════════

@router.get("/migration/all")
def get_all_migration_registrations(
    db=Depends(get_db),
    current_user=Depends(require_permission("validate_data")),
):
    try:
        registrations = (
            db.query(MigrationRegistrationModel)
            .filter(
                MigrationRegistrationModel.register_status == "SUBMITTED",
                # NOTE: same assumption as death above — verify the ward FK
                # column name against model/migration_registration_model.py.
                MigrationRegistrationModel.register_ward_id == current_user.user_ward_id,
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
                    MigrationRegistrationResponseAll.model_validate(
                        registration
                    ).model_dump(mode="json")
                    for registration in registrations
                ]
            }
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/migration/{migration_id}/approve")
def approve_migration_registration(
    migration_id: UUID,
    db=Depends(get_db),
    current_user=Depends(require_permission("validate_data")),
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
                detail=f"Only SUBMITTED registrations can be approved (current status: {registration.register_status.value})"
            )

        registration.register_status = MigrationRegistrationStatus.APPROVED
        db.commit()

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "status_code": 200,
                "message": "Registration APPROVED successfully",
                "data": None
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/migration/{migration_id}/reject")
def reject_migration_registration(
    migration_id: UUID,
    request: MigrationRejectRequest,
    db=Depends(get_db),
    current_user=Depends(require_permission("validate_data")),
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
                "data": serialize(reject, MigrationRejectResponse)
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# ══════════════════════════════════════════════
# COMPLAINT
# ══════════════════════════════════════════════

@router.get("/complaint/all")
def get_all_complaints(
    db=Depends(get_db),
    current_user=Depends(require_permission("validate_data")),
):
    try:
        complaints = (
            db.query(ComplaintModel)
            .filter(
                ComplaintModel.complaint_status == "SUBMITTED",
                ComplaintModel.complaint_ward_id == current_user.user_ward_id,
            )
            .all()
        )
        # print(complaints)

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
                ]
            }
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/complaint/{complaint_id}/approve")
def approve_complaint(
    complaint_id: UUID,
    db=Depends(get_db),
    current_user=Depends(require_permission("validate_data")),
):
    try:
        complaint = db.query(ComplaintModel).filter(
            ComplaintModel.complaint_id == complaint_id
        ).first()
        if not complaint:
            raise HTTPException(status_code=404, detail="Complaint not found")

        if complaint.complaint_status != ComplaintStatus.SUBMITTED:
            raise HTTPException(
                status_code=400,
                detail=f"Only SUBMITTED complaints can be approved (current status: {complaint.complaint_status.value})"
            )

        complaint.complaint_status = ComplaintStatus.APPROVED
        db.commit()

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "status_code": 200,
                "message": "Complaint APPROVED successfully",
                "data": None
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/complaint/{complaint_id}/reject")
def reject_complaint(
    complaint_id: UUID,
    request: ComplaintRejectRequest,
    db=Depends(get_db),
    current_user=Depends(require_permission("validate_data")),
):
    try:
        complaint = db.query(ComplaintModel).filter(
            ComplaintModel.complaint_id == complaint_id
        ).first()
        if not complaint:
            raise HTTPException(status_code=404, detail="Complaint not found")

        if complaint.complaint_status != ComplaintStatus.SUBMITTED:
            raise HTTPException(
                status_code=400,
                detail="Only SUBMITTED complaints can be rejected"
            )

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

# ══════════════════════════════════════════════
# RECOMMENDATION
# ══════════════════════════════════════════════
#
# THE FIX for "RoleSchema.DataValidationOfficer is not allowed to perform
# 'update_user'".
#
# Birth, Death, Migration and Complaint each had a data-validation stage
# here. Recommendation letters did not — the whole section was missing. So
# the DVO's "Edit Recommendation Letter" modal had no endpoint of its own to
# call, and its Approved/Reject buttons fell through to
# /v1/ward-chairperson/recommendation/{id}/approve, which requires
# "update_user" — a permission the DVO does not have and must not be given.
#
# This also broke the pipeline further downstream: ward_secretary_route
# queries for letters with register_status == "APPROVED", and nothing was
# ever setting a letter to APPROVED, so the secretary's queue stayed empty
# no matter how many letters citizens submitted.
#
# Stage owned here:  SUBMITTED --(DVO)--> APPROVED
# Then: APPROVED --(secretary)--> VERIFIED --(chairperson)--> CERTIFICATE_ISSUED

@router.get("/recommendation/all")
def get_all_recommendation_letters(
    db=Depends(get_db),
    current_user=Depends(require_permission("validate_data")),
):
    """Letters waiting on data validation — the DVO's queue."""
    try:
        letters = (
            db.query(RecommendationLetterModel)
            .filter(RecommendationLetterModel.register_status == RecommendationStatus.SUBMITTED)
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
                    RecommendationLetterResponse.model_validate(letter).model_dump(mode="json")
                    for letter in letters
                ],
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/recommendation/{letter_id}/approve")
def approve_recommendation_letter(
    letter_id: UUID,
    db=Depends(get_db),
    current_user=Depends(require_permission("validate_data")),
):
    try:
        letter = db.query(RecommendationLetterModel).filter(
            RecommendationLetterModel.letter_id == letter_id
        ).first()
        if not letter:
            raise HTTPException(status_code=404, detail="Letter not found")

        if letter.register_status != RecommendationStatus.SUBMITTED:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Only SUBMITTED letters can be approved by data validation "
                    f"(current status: {letter.register_status.value})"
                ),
            )

        # APPROVED, not VERIFIED. The DVO checks the data is correct; the ward
        # secretary is the one who verifies. Setting VERIFIED here would skip
        # the secretary entirely and hand the letter straight to the chairperson.
        letter.register_status = RecommendationStatus.APPROVED
        db.commit()

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "status_code": 200,
                "message": "Letter APPROVED successfully",
                "data": None,
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/recommendation/{letter_id}/reject")
def reject_recommendation_letter(
    letter_id: UUID,
    request: RecommendationRejectRequest,
    db=Depends(get_db),
    current_user=Depends(require_permission("validate_data")),
):
    try:
        letter = db.query(RecommendationLetterModel).filter(
            RecommendationLetterModel.letter_id == letter_id
        ).first()
        if not letter:
            raise HTTPException(status_code=404, detail="Letter not found")

        if letter.register_status != RecommendationStatus.SUBMITTED:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Only SUBMITTED letters can be rejected "
                    f"(current status: {letter.register_status.value})"
                ),
            )

        letter.register_status = RecommendationStatus.REJECTED

        reject = RecommendationRejectModel(
            letter_id=letter_id,
            reject_text=request.reject_text,
        )
        db.add(reject)
        db.commit()
        db.refresh(reject)

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "status_code": 200,
                "message": "Letter rejected successfully",
                "data": serialize(reject, RecommendationRejectResponse),
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))