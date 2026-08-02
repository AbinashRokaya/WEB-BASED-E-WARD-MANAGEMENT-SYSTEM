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

from model.ward_model import WardModel
from model.user_model import UserModel
from auth.current_user import require_permission

router = APIRouter(
    prefix="/v1/data-validation",
    tags=["Data Validation"]
)


def serialize(obj, schema):
    return schema.from_orm(obj).model_dump(mode="json")


# ══════════════════════════════════════════════
# BIRTH
# ══════════════════════════════════════════════

@router.get("/all")
def get_all_birth_registrations(
    db=Depends(get_db),
    current_user=Depends(require_permission("read_user")),
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
    current_user=Depends(require_permission("read_user")),
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
    current_user=Depends(require_permission("read_user")),
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
    current_user=Depends(require_permission("read_user")),
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
    current_user=Depends(require_permission("read_user")),
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
    current_user=Depends(require_permission("read_user")),
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
    current_user=Depends(require_permission("read_user")),
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
    current_user=Depends(require_permission("read_user")),
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
    current_user=Depends(require_permission("read_user")),
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
    current_user=Depends(require_permission("read_user")),
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
    current_user=Depends(require_permission("read_user")),
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
    current_user=Depends(require_permission("read_user")),
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