# router/migration_router.py
from fastapi import HTTPException, APIRouter, Depends
from fastapi.responses import JSONResponse
from uuid import UUID
from database.db import get_db
from model.migration_registration_model import (
    MigrationRegistrationModel, MigrationApplicantModel, MigrationAddressModel,
    MigrationDetailModel, MigrationFamilyMemberModel, MigrationRejectModel
)
from model.ward_model import WardModel
from model.user_model import UserModel
from enums.migration_enum import MigrationRegistrationStatus
from schema.migration_schema import (
    MigrationRegistrationRequest, MigrationRegistrationResponse,
    UpdateMigrationRegistrationRequest, RejectRequest, RejectResponse,
    UpdateApplicantRequest, UpdateFamilyMemberRequest, UpdateMigrationAddressRequest,
    MigrationRegistrationResponseAll
)
from auth.current_user import require_permission

router = APIRouter(
    prefix="/v1/migration-registration",
    tags=["migration-registration"]
)


def serialize(obj, schema):
    return schema.from_orm(obj).model_dump(mode="json")


@router.post("/")
def create_migration_registration(
    request: MigrationRegistrationRequest,
    db=Depends(get_db),
    current_user=Depends(require_permission("read_user"))
):
    try:
        ward = db.query(WardModel).filter(
            WardModel.ward_id == request.register_ward_id
        ).first()
        if not ward:
            raise HTTPException(status_code=404, detail="Ward not found")

        user = db.query(UserModel).filter(
            UserModel.user_id == current_user.user_id
        ).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        registration = MigrationRegistrationModel(
            register_ward_id=request.register_ward_id,
            register_submitted_by=current_user.user_id,
            register_status=MigrationRegistrationStatus.SUBMITTED,
            enclosure_citizenship_copy=request.enclosure_citizenship_copy,
            enclosure_address_proof=request.enclosure_address_proof,
            enclosure_destination_proof=request.enclosure_destination_proof,
            enclosure_photo_count=request.enclosure_photo_count,
            enclosure_other=request.enclosure_other,
        )
        db.add(registration)
        db.flush()

        applicant = MigrationApplicantModel(
            migration_id=registration.migration_id,
            **request.applicant.model_dump()
        )
        db.add(applicant)

        for address_data in request.addresses:
            address = MigrationAddressModel(
                migration_id=registration.migration_id,
                **address_data.model_dump()
            )
            db.add(address)

        migration_detail = MigrationDetailModel(
            migration_id=registration.migration_id,
            **request.migration_detail.model_dump()
        )
        db.add(migration_detail)

        for member_data in request.family_members:
            member = MigrationFamilyMemberModel(
                migration_id=registration.migration_id,
                **member_data.model_dump()
            )
            db.add(member)

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
                MigrationRegistrationModel.register_status == "SUBMITTED",
                MigrationRegistrationModel.register_ward_id == current_user.user_ward_id
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
            "enclosure_destination_proof", "enclosure_photo_count", "enclosure_other"
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
def approve_registration(migration_id: UUID, db=Depends(get_db)):
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