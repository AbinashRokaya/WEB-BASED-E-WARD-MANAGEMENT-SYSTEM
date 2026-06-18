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
    UpdateParentRequest, UpdateNomineeRequest, UpdateAddressRequest,AddressResponse

)
from auth.current_user import require_permission

router = APIRouter(
    prefix="/v1/birth-registration",
    tags=["birth-registration"]
)


def serialize(obj, schema):
    return schema.from_orm(obj).model_dump(mode="json")



@router.post("/")
def create_birth_registration(request: BirthRegistrationRequest, db=Depends(get_db),current_user=Depends(require_permission("read_user"))):
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

        
        parent_types = [p.parent_type for p in request.parents]
        if len(request.parents) < 1:
            raise HTTPException(status_code=400, detail="At least one parent is required")

       
        registration = BirthRegistrationModel(
            register_ward_id=request.register_ward_id,
            register_submitted_by=request.register_submitted_by,
            register_status=BirthRegistrationStatus.DRAFT
        )
        db.add(registration)
        db.flush()  

        
        child = ChildModel(
            registration_id=registration.registration_id,
            **request.child.model_dump()
        )
        db.add(child)

       
        for parent_data in request.parents:
            parent = ParentModel(
                registration_id=registration.registration_id,
                **parent_data.model_dump()
            )
            db.add(parent)

        
        for nominee_data in request.nominees:
            nominee = NomineeModel(
                nominee_registration_id=registration.registration_id,
                **nominee_data.model_dump()
            )
            db.add(nominee)

        
        address = AddressModel(
    registration_id=registration.registration_id,
    child_province=request.address.child_provience,
    child_district=request.address.child_district,
    child_municipality=request.address.child_municipality,
    child_ward_number=request.address.child_ward_number,
    child_tole=request.address.child_tole,
)
        db.add(address)

        db.commit()
        db.refresh(registration)

        return JSONResponse(
            status_code=201,
            content={
                "success": True,
                "status_code": 201,
                "message": "Birth registration created successfully",
                "data": serialize(registration, BirthRegistrationResponse)
            }
        )

    except HTTPException:
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

# ── Update a specific parent ───────────────────
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
                "data": serialize(parent, ParentResponse) if False else request.model_dump(exclude_unset=True)
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