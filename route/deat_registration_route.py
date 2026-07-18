# router/death_registration_router.py
from fastapi import HTTPException, APIRouter, Depends
from fastapi.responses import JSONResponse
from uuid import UUID
from database.db import get_db
from model.death_registration_route import (
    DeathRegistrationModel, DeceasedModel, DeathDetailModel,
    InformantModel, DeathAddressModel, DeathRejectModel
)
from model.ward_model import WardModel
from model.user_model import UserModel
from enums.death_enum import DeathRegistrationStatus
from schema.death_schema import (
    DeathRegistrationRequest, DeathRegistrationResponse,
    UpdateDeathRegistrationRequest, DeathRejectRequest, DeathRejectResponse,
    UpdateInformantRequest, UpdateDeathAddressRequest, DeathAddressResponse,
    DeathRegistrationResponseAll
)
from auth.current_user import require_permission

router = APIRouter(
    prefix="/v1/death-registration",
    tags=["death-registration"]
)


def serialize(obj, schema):
    return schema.from_orm(obj).model_dump(mode="json")


@router.post("/")
def create_death_registration(request: DeathRegistrationRequest, db=Depends(get_db), current_user=Depends(require_permission("read_user"))):
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

        registration = DeathRegistrationModel(
            register_ward_id=request.register_ward_id,
            register_submitted_by=current_user.user_id,
            register_status=DeathRegistrationStatus.SUBMITTED,
            registration_no=request.registration_no,
            page_no=request.page_no,
        )
        db.add(registration)
        db.flush()

        deceased = DeceasedModel(
            registration_id=registration.registration_id,
            **request.deceased.model_dump()
        )
        db.add(deceased)

        death_detail = DeathDetailModel(
            registration_id=registration.registration_id,
            **request.death_detail.model_dump()
        )
        db.add(death_detail)

        informant = InformantModel(
            registration_id=registration.registration_id,
            **request.informant.model_dump()
        )
        db.add(informant)

        # Nepali province/district/municipality are authoritative on the ward
        # record — pulled from there rather than trusted client input, same
        # pattern as birth registration's AddressModel. Nepali tole/other
        # per-person address fields come from the request.
        address = DeathAddressModel(
            registration_id=registration.registration_id,
            deceased_province=request.address.deceased_province,
            deceased_district=request.address.deceased_district,
            deceased_municipality=request.address.deceased_municipality,
            deceased_ward_number=request.address.deceased_ward_number,
            deceased_tole=request.address.deceased_tole,
            death_place_province=request.address.death_place_province,
            death_place_district=request.address.death_place_district,
            death_place_municipality=request.address.death_place_municipality,
            death_place_ward_number=request.address.death_place_ward_number,
            death_place_tole=request.address.death_place_tole,
            informant_province=request.address.informant_province,
            informant_district=request.address.informant_district,
            informant_municipality=request.address.informant_municipality,
            informant_ward_number=request.address.informant_ward_number,
            informant_tole=request.address.informant_tole,
            ward_nepali_province=ward.ward_nepali_province,
            ward_nepali_district=ward.ward_nepali_district,
            ward_nepali_municipality=ward.ward_nepali_municipality,
            ward_nepali_name=request.address.ward_nepali_name,
        )
        db.add(address)

        db.commit()
        db.refresh(registration)

        return JSONResponse(
            status_code=201,
            content={
                "success": True,
                "status_code": 201,
                "message": "Death registration created successfully",
                "data": serialize(registration, DeathRegistrationResponse)
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/all")
def get_all_death_registrations(db=Depends(get_db), current_user=Depends(require_permission("read_user"))):
    try:
        registrations = (
            db.query(DeathRegistrationModel)
            .filter(
                DeathRegistrationModel.register_status == "SUBMITTED",
                DeathRegistrationModel.register_ward_id == current_user.user_ward_id
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


@router.get("/")
def get_all_registrations(
    status: DeathRegistrationStatus = None,
    ward_id: UUID = None,
    db=Depends(get_db)
):
    try:
        query = db.query(DeathRegistrationModel)

        if status:
            query = query.filter(DeathRegistrationModel.register_status == status)
        if ward_id:
            query = query.filter(DeathRegistrationModel.register_ward_id == ward_id)

        registrations = query.all()

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "status_code": 200,
                "message": "Registrations fetched successfully",
                "total": len(registrations),
                "data": [serialize(r, DeathRegistrationResponse) for r in registrations]
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{registration_id}")
def get_registration(registration_id: UUID, db=Depends(get_db)):
    try:
        registration = db.query(DeathRegistrationModel).filter(
            DeathRegistrationModel.registration_id == registration_id
        ).first()

        if not registration:
            raise HTTPException(status_code=404, detail="Registration not found")

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "status_code": 200,
                "message": "Registration fetched successfully",
                "data": serialize(registration, DeathRegistrationResponse)
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{registration_id}")
def update_registration(
    registration_id: UUID,
    request: UpdateDeathRegistrationRequest,
    db=Depends(get_db)
):
    try:
        registration = db.query(DeathRegistrationModel).filter(
            DeathRegistrationModel.registration_id == registration_id
        ).first()
        if not registration:
            raise HTTPException(status_code=404, detail="Registration not found")

        if registration.register_status == DeathRegistrationStatus.APPROVED:
            raise HTTPException(
                status_code=400,
                detail="Approved registrations cannot be edited"
            )

        if request.register_status:
            registration.register_status = request.register_status

        if request.registration_no is not None:
            registration.registration_no = request.registration_no

        if request.page_no is not None:
            registration.page_no = request.page_no

        if request.deceased and registration.deceased:
            deceased_data = request.deceased.model_dump(exclude_unset=True)
            for field, value in deceased_data.items():
                setattr(registration.deceased, field, value)

        if request.death_detail and registration.death_detail:
            death_detail_data = request.death_detail.model_dump(exclude_unset=True)
            for field, value in death_detail_data.items():
                setattr(registration.death_detail, field, value)

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
                "data": serialize(registration, DeathRegistrationResponse)
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
        registration = db.query(DeathRegistrationModel).filter(
            DeathRegistrationModel.registration_id == registration_id
        ).first()
        if not registration:
            raise HTTPException(status_code=404, detail="Registration not found")

        if registration.register_status != DeathRegistrationStatus.DRAFT:
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
# NESTED ROUTES — Informant / Reject / Approve
# ══════════════════════════════════════════════

@router.put("/{registration_id}/informant")
def update_informant(
    registration_id: UUID,
    request: UpdateInformantRequest,
    db=Depends(get_db)
):
    try:
        informant = db.query(InformantModel).filter(
            InformantModel.registration_id == registration_id
        ).first()
        if not informant:
            raise HTTPException(status_code=404, detail="Informant not found")

        for field, value in request.model_dump(exclude_unset=True).items():
            setattr(informant, field, value)

        db.commit()
        db.refresh(informant)

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "status_code": 200,
                "message": "Informant updated successfully",
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
    request: DeathRejectRequest,
    db=Depends(get_db)
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


@router.post("/{registration_id}/approve")
def approve_registration(registration_id: UUID, db=Depends(get_db)):
    try:
        registration = db.query(DeathRegistrationModel).filter(
            DeathRegistrationModel.registration_id == registration_id
        ).first()
        if not registration:
            raise HTTPException(status_code=404, detail="Registration not found")

        if registration.register_status != DeathRegistrationStatus.SUBMITTED:
            raise HTTPException(
                status_code=400,
                detail="Only SUBMITTED registrations can be approved"
            )

        registration.register_status = DeathRegistrationStatus.APPROVED
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


@router.get("/ward-chairperson/all")
def get_all_ward_chairperson_registrations(
    db=Depends(get_db),
    current_user=Depends(require_permission("read_user"))
):
    try:
        registrations = (
            db.query(DeathRegistrationModel)
            .filter(DeathRegistrationModel.register_ward_id == current_user.user_ward_id)
            .all()
        )
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "status_code": 200,
                "message": "Registrations fetched successfully",
                "total": len(registrations),
                "data": [
                    DeathRegistrationResponseAll.model_validate(r).model_dump(mode="json")
                    for r in registrations
                ],
            },
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))