# router/birth_registration_router.py
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
    prefix="/v1/citizen",
    tags=["citizen"]
)


def serialize(obj, schema):
    return schema.from_orm(obj).model_dump(mode="json")

# router/birth_registration_router.py

@router.get("/birth/all")
def get_all_birth_registrations(db=Depends(get_db), current_user=Depends(require_permission("read_user"))):
    try:
        registrations = (
            db.query(BirthRegistrationModel)
            # FIX: Change submitted_by_user to register_submitted_by
            .filter(BirthRegistrationModel.register_submitted_by == current_user.user_id)
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

@router.get("/birth/{registration_id}")
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