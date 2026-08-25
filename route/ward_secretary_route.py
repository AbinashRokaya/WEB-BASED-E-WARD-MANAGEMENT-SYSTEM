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

from model.ward_model import WardModel
from model.user_model import UserModel
from auth.current_user import require_permission

router = APIRouter(
    prefix="/v1/ward-secretary",
    tags=["ward-secretary"]
)
# ── Recommendation ──────────────────────────────────────
from model.recommendation_model import RecommendationLetterModel, RecommendationRejectModel
from enums.recommendation_enum import RecommendationStatus
from schema.recommendation_schema import (
    RejectRequest as RecommendationRejectRequest,
    RejectResponse as RecommendationRejectResponse,
    RecommendationLetterResponse,
)
# ── Complaint ────────────────────────────────────────────
from model.complaint_model import ComplaintModel, ComplaintRejectModel
from enums.complaint_enum import ComplaintStatus
from schema.complaint_schema import (
    ComplaintRejectRequest, ComplaintRejectResponse, ComplaintResponseAll
)

from enums.complaint_enum import ComplaintStatus, ComplaintCategory, requires_escalation
from route.complaint_route import _save_complaint_document  # reuse the same saver
from fastapi import File, Form, UploadFile
from typing import Optional

def serialize(obj, schema):
    return schema.from_orm(obj).model_dump(mode="json")



# ══════════════════════════════════════════════
# BIRTH
# ══════════════════════════════════════════════

@router.get("/all")
def get_all_birth_registrations(db=Depends(get_db)):
    try:
        registrations = (
            db.query(BirthRegistrationModel).filter(BirthRegistrationModel.register_status == "APPROVED")
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
def approve_registration(registration_id: UUID, db=Depends(get_db)):
    try:
        registration = db.query(BirthRegistrationModel).filter(
            BirthRegistrationModel.registration_id == registration_id
        ).first()
        if not registration:
            raise HTTPException(status_code=404, detail="Registration not found")

        if registration.register_status != BirthRegistrationStatus.APPROVED:
            raise HTTPException(
                status_code=400,
                detail=f"Only APPROVED registrations can be verified (current status: {registration.register_status.value})"
            )

        registration.register_status = BirthRegistrationStatus.VERIFIED
        db.commit()

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "status_code": 200,
                "message": "Registration VERIFIED successfully",
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
    db=Depends(get_db)
):
    try:
        registration = db.query(BirthRegistrationModel).filter(
            BirthRegistrationModel.registration_id == registration_id
        ).first()
        if not registration:
            raise HTTPException(status_code=404, detail="Registration not found")

        if registration.register_status != BirthRegistrationStatus.VERIFIED:
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
def get_all_death_registrations(db=Depends(get_db)):
    try:
        registrations = (
            db.query(DeathRegistrationModel)
            .filter(DeathRegistrationModel.register_status == "APPROVED")
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
def approve_death_registration(registration_id: UUID, db=Depends(get_db)):
    try:
        registration = db.query(DeathRegistrationModel).filter(
            DeathRegistrationModel.registration_id == registration_id
        ).first()
        if not registration:
            raise HTTPException(status_code=404, detail="Registration not found")

        if registration.register_status != DeathRegistrationStatus.APPROVED:
            raise HTTPException(
                status_code=400,
                detail=f"Only APPROVED registrations can be verified (current status: {registration.register_status.value})"
            )

        registration.register_status = DeathRegistrationStatus.VERIFIED
        db.commit()

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "status_code": 200,
                "message": "Registration VERIFIED successfully",
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
    db=Depends(get_db)
):
    try:
        registration = db.query(DeathRegistrationModel).filter(
            DeathRegistrationModel.registration_id == registration_id
        ).first()
        if not registration:
            raise HTTPException(status_code=404, detail="Registration not found")

        if registration.register_status != DeathRegistrationStatus.VERIFIED:
            raise HTTPException(
                status_code=400,
                detail="Only VERIFIED registrations can be rejected"
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
def get_all_migration_registrations(db=Depends(get_db)):
    try:
        registrations = (
            db.query(MigrationRegistrationModel)
            .filter(MigrationRegistrationModel.register_status == "APPROVED")
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
def approve_migration_registration(migration_id: UUID, db=Depends(get_db)):
    try:
        registration = db.query(MigrationRegistrationModel).filter(
            MigrationRegistrationModel.migration_id == migration_id
        ).first()
        if not registration:
            raise HTTPException(status_code=404, detail="Registration not found")

        if registration.register_status != MigrationRegistrationStatus.APPROVED:
            raise HTTPException(
                status_code=400,
                detail=f"Only APPROVED registrations can be verified (current status: {registration.register_status.value})"
            )

        registration.register_status = MigrationRegistrationStatus.VERIFIED
        db.commit()

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "status_code": 200,
                "message": "Registration VERIFIED successfully",
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
    db=Depends(get_db)
):
    try:
        registration = db.query(MigrationRegistrationModel).filter(
            MigrationRegistrationModel.migration_id == migration_id
        ).first()
        if not registration:
            raise HTTPException(status_code=404, detail="Registration not found")

        if registration.register_status != MigrationRegistrationStatus.VERIFIED:
            raise HTTPException(
                status_code=400,
                detail="Only VERIFIED registrations can be rejected"
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
# RECOMMENDATION
# ══════════════════════════════════════════════

@router.get("/recommendation/all")
def get_all_recommendation_letters(db=Depends(get_db)):
    try:
        letters = (
            db.query(RecommendationLetterModel)
            .filter(RecommendationLetterModel.register_status == "APPROVED")
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
                ]
            }
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/recommendation/{letter_id}/approve")
def approve_recommendation_letter(letter_id: UUID, db=Depends(get_db)):
    try:
        letter = db.query(RecommendationLetterModel).filter(
            RecommendationLetterModel.letter_id == letter_id
        ).first()
        if not letter:
            raise HTTPException(status_code=404, detail="Letter not found")

        if letter.register_status != RecommendationStatus.APPROVED:
            raise HTTPException(
                status_code=400,
                detail=f"Only APPROVED letters can be verified (current status: {letter.register_status.value})"
            )

        letter.register_status = RecommendationStatus.VERIFIED
        db.commit()

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "status_code": 200,
                "message": "Letter VERIFIED successfully",
                "data": None
            }
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
    db=Depends(get_db)
):
    try:
        letter = db.query(RecommendationLetterModel).filter(
            RecommendationLetterModel.letter_id == letter_id
        ).first()
        if not letter:
            raise HTTPException(status_code=404, detail="Letter not found")

        if letter.register_status != RecommendationStatus.VERIFIED:
            raise HTTPException(
                status_code=400,
                detail="Only VERIFIED letters can be rejected"
            )

        letter.register_status = RecommendationStatus.REJECTED

        reject = RecommendationRejectModel(
            letter_id=letter_id,
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
                "message": "Letter rejected successfully",
                "data": serialize(reject, RecommendationRejectResponse)
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
def get_all_ward_secretary_complaints(db=Depends(get_db), current_user=Depends(require_permission("read_user"))):
    """Secretary's queue — every APPROVED complaint in their ward,
    regardless of whether it will end up resolved directly or escalated."""
    try:
        complaints = (
            db.query(ComplaintModel)
            .filter(
                ComplaintModel.complaint_ward_id == current_user.user_ward_id,
                ComplaintModel.complaint_status == ComplaintStatus.APPROVED,
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
                ]
            }
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/complaint/{complaint_id}/resolve")
def resolve_complaint_directly(
    complaint_id: UUID,
    resolution_note: str = Form(..., min_length=10, max_length=1000),
    resolution_image: Optional[UploadFile] = File(None),
    db=Depends(get_db),
    current_user=Depends(require_permission("update_user")),
):
    """Secretary resolves ordinary complaints directly — no chairperson needed."""
    try:
        complaint = db.query(ComplaintModel).filter(
            ComplaintModel.complaint_id == complaint_id
        ).first()
        if not complaint:
            raise HTTPException(status_code=404, detail="Complaint not found")

        if complaint.complaint_status != ComplaintStatus.APPROVED:
            raise HTTPException(
                status_code=400,
                detail=f"Only APPROVED complaints can be resolved here (current status: {complaint.complaint_status.value})",
            )

        if requires_escalation(complaint.complaint_category):
            raise HTTPException(
                status_code=400,
                detail="This category must be escalated to the ward chairperson, not resolved directly",
            )

        complaint.resolution_note = resolution_note.strip()
        if resolution_image:
            complaint.resolution_image_path = _save_complaint_document(
                complaint_id, resolution_image, "resolution"
            )

        complaint.complaint_status = ComplaintStatus.RESOLVED
        db.commit()

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "status_code": 200,
                "message": "Complaint resolved directly by secretary",
                "data": None,
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/complaint/{complaint_id}/approve")
def forward_complaint_to_chairperson(
    complaint_id: UUID,
    db=Depends(get_db),
    current_user=Depends(require_permission("update_user")),
):
    """Secretary forwards escalation-required complaints to the chairperson.
    Blocked for ordinary categories — those must use /resolve instead."""
    try:
        complaint = db.query(ComplaintModel).filter(
            ComplaintModel.complaint_id == complaint_id
        ).first()
        if not complaint:
            raise HTTPException(status_code=404, detail="Complaint not found")

        if complaint.complaint_status != ComplaintStatus.APPROVED:
            raise HTTPException(
                status_code=400,
                detail=f"Only APPROVED complaints can be forwarded (current status: {complaint.complaint_status.value})",
            )

        if not requires_escalation(complaint.complaint_category):
            raise HTTPException(
                status_code=400,
                detail="This category should be resolved directly, not forwarded",
            )

        complaint.complaint_status = ComplaintStatus.VERIFIED
        db.commit()

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "status_code": 200,
                "message": "Complaint forwarded to chairperson",
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
    db=Depends(get_db)
):
    try:
        letter = db.query(RecommendationLetterModel).filter(
            RecommendationLetterModel.letter_id == letter_id
        ).first()
        if not letter:
            raise HTTPException(status_code=404, detail="Letter not found")

        if letter.register_status != RecommendationStatus.APPROVED:          # ← was VERIFIED
            raise HTTPException(
                status_code=400,
                detail=f"Only APPROVED letters can be rejected (current status: {letter.register_status.value})"  # ← updated message
            )

        letter.register_status = RecommendationStatus.REJECTED

        reject = RecommendationRejectModel(
            letter_id=letter_id,
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
                "message": "Letter rejected successfully",
                "data": serialize(reject, RecommendationRejectResponse)
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))