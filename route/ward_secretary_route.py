from fastapi import HTTPException, APIRouter, Depends
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
    UpdateParentRequest, UpdateNomineeRequest, UpdateAddressRequest,AddressResponse,BirthRegistrationResponseAll

)
from auth.current_user import require_permission

router = APIRouter(
    prefix="/v1/ward-secretary",
    tags=["ward-secretary"]
)

def serialize(obj, schema):
    return schema.from_orm(obj).model_dump(mode="json")


@router.get("/all")
def get_all_birth_registrations(db=Depends(get_db)):
    try:
        registrations = (
            db.query(BirthRegistrationModel).filter(BirthRegistrationModel.register_status=="APPROVED")
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
                detail="Only SUBMITTED registrations can be approved"
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

