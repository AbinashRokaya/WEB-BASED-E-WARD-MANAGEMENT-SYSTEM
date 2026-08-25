from fastapi import HTTPException, APIRouter, BackgroundTasks, Depends, File, Form, UploadFile
from fastapi.responses import JSONResponse
from uuid import UUID
from database.db import get_db
from typing import Optional
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
from services.certificate_service import (
    issue_certificate_for_registration,
)
from services.death_certificate_service import (
    issue_certificate_for_death_registration,
)
from services.migration_certificate_service import (
    issue_certificate_for_migration_registration,
)
from model.recommendation_model import RecommendationLetterModel, RecommendationRejectModel
from enums.recommendation_enum import RecommendationStatus
from schema.recommendation_schema import (
    RejectRequest as RecommendationRejectRequest,
    RejectResponse as RecommendationRejectResponse,
    RecommendationLetterResponse,
)
from services.recommendation_certificate_service import (
    issue_certificate_for_recommendation_letter,
)
from services.notification_service import notify_certificate_issued
from route.complaint_route import _save_complaint_document  # reuse the same saver
from model.complaint_model import ComplaintModel, ComplaintRejectModel
from enums.complaint_enum import ComplaintStatus
from schema.complaint_schema import (
    ComplaintRejectRequest, ComplaintRejectResponse, ComplaintResponseAll
)

router = APIRouter(
    prefix="/v1/ward-chairperson",
    tags=["ward-chairperson"]
)


def serialize(obj, schema):
    return schema.from_orm(obj).model_dump(mode="json")

# ══════════════════════════════════════════════
# BIRTH
# ══════════════════════════════════════════════

@router.post("/{registration_id}/approve")
def approve_registration(
    registration_id: UUID,
    background_tasks: BackgroundTasks,
    db=Depends(get_db),
    current_user=Depends(require_permission("issue_certificate")),
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
                detail=f"Only VERIFIED registrations can be approved (current status: {registration.register_status.value})"
            )

        certificate = issue_certificate_for_registration(registration, db, current_user.user_id)

        # THE FIX: this path issued the certificate and told nobody.
        # Same notification the /issue-certificate endpoint sends.
        emailed = notify_certificate_issued(background_tasks, "birth", registration, certificate)

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "status_code": 200,
                "message": "Certificate issued successfully",
                "data": {
                    "certificate_no": certificate.certificate_no,
                    "notification_sent": emailed,
                },
            }
        )

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/all")
def get_all_birth_registrations(db=Depends(get_db)):
    try:
        registrations = (
            db.query(BirthRegistrationModel).filter(BirthRegistrationModel.register_status == "VERIFIED")
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

        if registration.register_status != BirthRegistrationStatus.CERTIFICATE_ISSUED:
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

@router.post("/death/{registration_id}/approve")
def approve_death_registration(
    registration_id: UUID,
    background_tasks: BackgroundTasks,
    db=Depends(get_db),
    current_user=Depends(require_permission("issue_certificate")),
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
                detail=f"Only VERIFIED registrations can be approved (current status: {registration.register_status.value})"
            )

        certificate = issue_certificate_for_death_registration(registration, db, current_user.user_id)

        # THE FIX: this path issued the certificate and told nobody.
        # Same notification the /issue-certificate endpoint sends.
        emailed = notify_certificate_issued(background_tasks, "death", registration, certificate)

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "status_code": 200,
                "message": "Certificate issued successfully",
                "data": {
                    "certificate_no": certificate.certificate_no,
                    "notification_sent": emailed,
                },
            }
        )

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/death/all")
def get_all_death_registrations(db=Depends(get_db)):
    try:
        registrations = (
            db.query(DeathRegistrationModel)
            .filter(DeathRegistrationModel.register_status == "VERIFIED")
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

        if registration.register_status != DeathRegistrationStatus.CERTIFICATE_ISSUED:
            raise HTTPException(
                status_code=400,
                detail="Only CERTIFICATE_ISSUED registrations can be rejected"
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

@router.post("/migration/{migration_id}/approve")
def approve_migration_registration(
    migration_id: UUID,
    background_tasks: BackgroundTasks,
    db=Depends(get_db),
    current_user=Depends(require_permission("issue_certificate")),
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
                detail=f"Only VERIFIED registrations can be approved (current status: {registration.register_status.value})"
            )

        certificate = issue_certificate_for_migration_registration(registration, db, current_user.user_id)

        # THE FIX: this path issued the certificate and told nobody.
        # Same notification the /issue-certificate endpoint sends.
        emailed = notify_certificate_issued(background_tasks, "migration", registration, certificate)

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "status_code": 200,
                "message": "Certificate issued successfully",
                "data": {
                    "certificate_no": certificate.certificate_no,
                    "notification_sent": emailed,
                },
            }
        )

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/migration/all")
def get_all_migration_registrations(db=Depends(get_db)):
    try:
        registrations = (
            db.query(MigrationRegistrationModel)
            .filter(MigrationRegistrationModel.register_status == "VERIFIED")
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

        if registration.register_status != MigrationRegistrationStatus.CERTIFICATE_ISSUED:
            raise HTTPException(
                status_code=400,
                detail="Only CERTIFICATE_ISSUED registrations can be rejected"
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
#
# NOTE: recommendation letters have a ward-secretary verification step —
# confirmed against the DB, letters can sit at register_status = VERIFIED
# (that transition happens in a ward-secretary router not shown here,
# analogous to Birth/Death/Migration's secretary stage). The chairperson
# only ever acts on VERIFIED letters, same as the other three types.
# issue_certificate_for_recommendation_letter (the service) now sets the
# terminal status to CERTIFICATE_ISSUED — matching BirthRegistrationModel's
# naming exactly — so /all and the frontend config key off that.

@router.post("/recommendation/{letter_id}/approve")
def approve_recommendation_letter(
    letter_id: UUID,
    background_tasks: BackgroundTasks,
    db=Depends(get_db),
    current_user=Depends(require_permission("issue_certificate")),
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
                detail=f"Only VERIFIED letters can be approved (current status: {letter.register_status.value})"
            )

        certificate = issue_certificate_for_recommendation_letter(letter, db, current_user.user_id)

        # THE FIX: this path issued the certificate and told nobody.
        # Same notification the /issue-certificate endpoint sends.
        emailed = notify_certificate_issued(background_tasks, "recommendation", letter, certificate)

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "status_code": 200,
                "message": "Certificate issued successfully",
                "data": {
                    "certificate_no": certificate.certificate_no,
                    "notification_sent": emailed,
                },
            }
        )

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/recommendation/all")
def get_all_recommendation_letters(db=Depends(get_db)):
    try:
        # Return everything relevant to the chairperson's queue — both the
        # still-pending VERIFIED letters (verified by the ward secretary,
        # awaiting the chairperson's signature) and the ones already
        # resolved (CERTIFICATE_ISSUED / REJECTED) — so the frontend can
        # bucket them into its "Pending Signatures" vs "Issued Certificates"
        # tabs client-side, the same way the other three types do.
        # SUBMITTED letters are deliberately excluded — those haven't been
        # verified yet and aren't the chairperson's to act on.
        letters = (
            db.query(RecommendationLetterModel)
            .filter(
                RecommendationLetterModel.register_status.in_([
                    RecommendationStatus.VERIFIED,
                    RecommendationStatus.CERTIFICATE_ISSUED,
                    RecommendationStatus.REJECTED,
                ])
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
                    RecommendationLetterResponse.model_validate(letter).model_dump(mode="json")
                    for letter in letters
                ]
            }
        )

    except Exception as e:
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
    
@router.get("/ward-chairperson/all")
def get_all_ward_chairperson_complaints(db=Depends(get_db), current_user=Depends(require_permission("read_user"))):
    try:
        complaints = (
            db.query(ComplaintModel)
            .filter(
                ComplaintModel.complaint_ward_id == current_user.user_ward_id,
                ComplaintModel.complaint_status == ComplaintStatus.VERIFIED,  # was FORWARDED/ESCALATED
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
    
# ══════════════════════════════════════════════
# COMPLAINT
# ══════════════════════════════════════════════



@router.post("/complaint/{complaint_id}/approve")
def approve_complaint(
    complaint_id: UUID,
    resolution_note: str = Form(..., min_length=10, max_length=1000),
    resolution_image: Optional[UploadFile] = File(None),
    db=Depends(get_db),
    current_user=Depends(require_permission("update_user")),
):
    try:
        complaint = db.query(ComplaintModel).filter(
            ComplaintModel.complaint_id == complaint_id
        ).first()
        if not complaint:
            raise HTTPException(status_code=404, detail="Complaint not found")

        if complaint.complaint_status != ComplaintStatus.VERIFIED:
            raise HTTPException(
                status_code=400,
                detail=f"Only VERIFIED complaints can be approved (current status: {complaint.complaint_status.value})"
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
                "message": "Complaint resolved successfully",
                "data": None
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/complaint/all")
def get_all_ward_chairperson_complaints(db=Depends(get_db), current_user=Depends(require_permission("read_user"))):
    try:
        complaints = (
            db.query(ComplaintModel)
            .filter(
                ComplaintModel.complaint_ward_id == current_user.user_ward_id,
                ComplaintModel.complaint_status.in_([
                    ComplaintStatus.VERIFIED,
                    ComplaintStatus.RESOLVED,
                    ComplaintStatus.REJECTED,
                ]),
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/complaint/{complaint_id}/reject")
def reject_complaint(
    complaint_id: UUID,
    request: ComplaintRejectRequest,
    db=Depends(get_db),
    current_user=Depends(require_permission("update_user")),
):
    try:
        complaint = db.query(ComplaintModel).filter(
            ComplaintModel.complaint_id == complaint_id
        ).first()
        if not complaint:
            raise HTTPException(status_code=404, detail="Complaint not found")

        if complaint.complaint_status != ComplaintStatus.VERIFIED:
            raise HTTPException(
                status_code=400,
                detail="Only VERIFIED complaints can be rejected"
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