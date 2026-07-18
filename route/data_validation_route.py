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
    prefix="/v1/data-validation",
    tags=["Data Validation"]
)
def serialize(obj, schema):
    return schema.from_orm(obj).model_dump(mode="json")


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

