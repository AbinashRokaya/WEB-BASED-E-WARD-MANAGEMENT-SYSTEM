from fastapi import HTTPException, APIRouter, Depends
from fastapi.responses import JSONResponse
from database.db import get_db
from model.ward_model import WardModel
from schema.admin_schema import CreateWordRequest, CreateWordResponse,UpdateWardRequest,AssignOfficerRequest, UpdateOfficerRequest, OfficerResponse,GetAllWardResponse
from model.user_model import UserModel
from schema.user_schema import RoleSchema
from typing import List


router = APIRouter(
    prefix="/v1/admin",
    tags=["admin"]
)


@router.post("/ward")
def create_ward(request: CreateWordRequest, db=Depends(get_db)):
    try:
        
        existing_ward = db.query(WardModel).filter(
            WardModel.ward_province == request.ward_province,
            WardModel.ward_district == request.ward_district,
            WardModel.ward_municipality == request.ward_municipality,
            WardModel.ward_name == request.ward_name
        ).first()

       
        if existing_ward:
            raise HTTPException(
                status_code=400,
                detail="Ward already exists in this municipality"
            )

        new_ward = WardModel(
            ward_no=request.ward_no,
            ward_municipality=request.ward_municipality,  
            ward_district=request.ward_district,
            ward_province=request.ward_province,        
            ward_contact_number=request.ward_contact_number,
            ward_email=request.ward_email,
            ward_name=request.ward_name
        )

        db.add(new_ward)     
        db.commit()
        db.refresh(new_ward)

        new_ward_response = CreateWordResponse(
            ward_id=new_ward.ward_id,
            ward_no=new_ward.ward_no,
            ward_name=new_ward.ward_name,
            ward_municipality=new_ward.ward_municipality,  
            ward_district=new_ward.ward_district,
            ward_province=new_ward.ward_province,
            ward_contact_number=new_ward.ward_contact_number,
            ward_email=new_ward.ward_email
        )

        return JSONResponse(
            status_code=201,
            content={
                "success": True,
                "status_code": 201,
                "message": "New ward is created",
                "data": new_ward_response.model_dump()
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        
        raise HTTPException(status_code=500, detail=str(e))
    
@router.get("/ward")
def get_all_ward(db=Depends(get_db)):
    try:
        ward=db.query(WardModel).all()
        if not ward:
            raise HTTPException(status_code=404, detail="Ward not found")
        
        ward_list=[CreateWordResponse(
             ward_id=w.ward_id,
            ward_no=w.ward_no,
            ward_name=w.ward_name,
            ward_municipality=w.ward_municipality,  
            ward_district=w.ward_district,
            ward_province=w.ward_province,
            ward_contact_number=w.ward_contact_number,
            ward_email=w.ward_email
        )for w in ward]
        response_data= GetAllWardResponse(ward_list=ward_list)

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "status_code": 200,
                "message": "New ward is created",
                "data":response_data.model_dump(mode="json")
            }
        )

    except HTTPException:
            raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/ward/{ward_id}")
def update_ward(ward_id: str, request: UpdateWardRequest, db=Depends(get_db)):
    try:
        ward = db.query(WardModel).filter(WardModel.ward_id == ward_id).first()
        if not ward:
            raise HTTPException(status_code=404, detail="Ward not found")

        duplicate = db.query(WardModel).filter(
            WardModel.ward_province == (request.ward_province or ward.ward_province),
            WardModel.ward_district == (request.ward_district or ward.ward_district),
            WardModel.ward_municipality == (request.ward_municipality or ward.ward_municipality),
            WardModel.ward_name == (request.ward_name or ward.ward_name),
            WardModel.ward_id != ward_id
        ).first()

        if duplicate:
            raise HTTPException(
                status_code=400,
                detail="A ward with the same name already exists in this municipality"
            )

       
        update_data = request.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(ward, field, value)

        db.commit()
        db.refresh(ward)

        updated_ward_response = CreateWordResponse(
            ward_id=ward.ward_id,
            ward_no=ward.ward_no,
            ward_name=ward.ward_name,
            ward_municipality=ward.ward_municipality,
            ward_district=ward.ward_district,
            ward_province=ward.ward_province,
            ward_contact_number=ward.ward_contact_number,
            ward_email=ward.ward_email
        )

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "status_code": 200,
                "message": "Ward updated successfully",
                "data": updated_ward_response.model_dump(mode="json")
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    

@router.delete("/ward/{ward_id}")
def delete_ward(ward_id: int, db=Depends(get_db)):
    try:
        # Check if ward exists
        ward = db.query(WardModel).filter(WardModel.ward_id == ward_id).first()
        if not ward:
            raise HTTPException(status_code=404, detail="Ward not found")

        db.delete(ward)
        db.commit()

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "status_code": 200,
                "message": f"Ward with id {ward_id} deleted successfully",
                "data": None
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    
OFFICER_ROLES = [
    RoleSchema.WardChairperson,
    RoleSchema.WardSecretary,
    RoleSchema.DataValidationOfficer
]


def get_ward(db, municipality: str, ward_number: int):
    
    ward = db.query(WardModel).filter(
        WardModel.ward_municipality == municipality,
        WardModel.ward_no == ward_number
    ).first()
    if not ward:
        raise HTTPException(
            status_code=404,
            detail=f"Ward {ward_number} not found in municipality {municipality}"
        )
    return ward

@router.post("/user/")
def assign_officer(request: AssignOfficerRequest, db=Depends(get_db)):
    try:
       
        if request.user_role not in OFFICER_ROLES:
            raise HTTPException(
                status_code=400,
                detail=f"Role must be one of: {[r.value for r in OFFICER_ROLES]}"
            )

        
        get_ward(db, request.user_municipality, request.user_ward_number)

        
        if db.query(UserModel).filter(
            UserModel.user_name == request.user_name
        ).first():
            raise HTTPException(status_code=400, detail="Username already exists")

        
        if db.query(UserModel).filter(
            UserModel.user_phone_number == request.user_phone_number
        ).first():
            raise HTTPException(status_code=400, detail="Phone number already exists")

        
        if db.query(UserModel).filter(
            UserModel.user_citizenship_number == request.user_citizenship_number
        ).first():
            raise HTTPException(status_code=400, detail="Citizenship number already exists")

        #
        existing_role = db.query(UserModel).filter(
            UserModel.user_municipality == request.user_municipality,
            UserModel.user_ward_number == request.user_ward_number,
            UserModel.user_role == request.user_role
        ).first()

        if existing_role:
            raise HTTPException(
                status_code=400,
                detail=f"A {request.user_role.value} is already assigned to ward {request.user_ward_number}"
            )

        new_officer = UserModel(
            user_name=request.user_name,
            user_phone_number=request.user_phone_number,
            user_citizenship_number=request.user_citizenship_number,
            user_provience=request.user_province,  
            user_district=request.user_district,
            user_municipality=request.user_municipality,
            user_ward_number=request.user_ward_number,
            user_role=request.user_role
        )

        db.add(new_officer)
        db.commit()
        db.refresh(new_officer)

        response=OfficerResponse(
            user_id=new_officer.user_id,
            user_name= new_officer.user_name,
    user_phone_number= new_officer.user_phone_number,
    user_citizenship_number= new_officer.user_citizenship_number,
    user_province= new_officer.user_provience,
    user_district= new_officer.user_district,
    user_municipality= new_officer.user_municipality,
    user_ward_number= new_officer.user_ward_number,
    user_role= new_officer.user_role
        )

        return JSONResponse(
            status_code=201,
            content={
                "success": True,
                "status_code": 201,
                "message": "Officer assigned successfully",
                "data": response.model_dump()
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/user/")
def get_all_officers(
    ward_number: int = None,
    municipality: str = None,
    role: RoleSchema = None,
    db=Depends(get_db)
):
    try:
        query = db.query(UserModel).filter(UserModel.user_role.in_(OFFICER_ROLES))

        if ward_number:
            query = query.filter(UserModel.user_ward_number == ward_number)
        if municipality:
            query = query.filter(UserModel.user_municipality == municipality)
        if role:
            query = query.filter(UserModel.user_role == role)

        officers = query.all()

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "status_code": 200,
                "message": "Officers fetched successfully",
                "total": len(officers),
                "data": [OfficerResponse.from_orm(o).model_dump() for o in officers]
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@router.get("/user/{user_id}")
def get_officer(user_id: int, db=Depends(get_db)):
    try:
        officer = db.query(UserModel).filter(
            UserModel.user_id == user_id,
            UserModel.user_role.in_(OFFICER_ROLES)
        ).first()

        if not officer:
            raise HTTPException(status_code=404, detail="Officer not found")

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "status_code": 200,
                "message": "Officer fetched successfully",
                "data": OfficerResponse.from_orm(officer).model_dump()
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@router.get("/users/officers")
def get_all_officers(db=Depends(get_db)):
    try:
        officers = db.query(UserModel).filter(
            UserModel.user_role != RoleSchema.Citizen.value
        ).all()

        if not officers:
            raise HTTPException(
                status_code=404,
                detail="No officers found"
            )

        officer_list = [
            OfficerResponse.model_validate(officer).model_dump()
            for officer in officers
        ]

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "status_code": 200,
                "message": "Officers fetched successfully",
                "data": officer_list
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )
    
@router.put("/user/{user_id}")
def update_officer(user_id: int, request: UpdateOfficerRequest, db=Depends(get_db)):
    try:
        officer = db.query(UserModel).filter(
            UserModel.user_id == user_id,
            UserModel.user_role.in_(OFFICER_ROLES)
        ).first()

        if not officer:
            raise HTTPException(status_code=404, detail="Officer not found")

        update_data = request.model_dump(exclude_unset=True)

        
        if "user_role" in update_data and update_data["user_role"] not in OFFICER_ROLES:
            raise HTTPException(
                status_code=400,
                detail=f"Role must be one of: {[r.value for r in OFFICER_ROLES]}"
            )

    
        new_municipality = update_data.get("user_municipality", officer.user_municipality)
        new_ward_number = update_data.get("user_ward_number", officer.user_ward_number)
        new_role = update_data.get("user_role", officer.user_role)

        if any(k in update_data for k in ["user_municipality", "user_ward_number", "user_role"]):
    
            get_ward(db, new_municipality, new_ward_number)

            duplicate_role = db.query(UserModel).filter(
                UserModel.user_municipality == new_municipality,
                UserModel.user_ward_number == new_ward_number,
                UserModel.user_role == new_role,
                UserModel.user_id != user_id       
            ).first()

            if duplicate_role:
                raise HTTPException(
                    status_code=400,
                    detail=f"A {new_role.value} is already assigned to ward {new_ward_number}"
                )

    
        if "user_province" in update_data:
            update_data["user_provience"] = update_data.pop("user_province")

        for field, value in update_data.items():
            setattr(officer, field, value)

        db.commit()
        db.refresh(officer)

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "status_code": 200,
                "message": "Officer updated successfully",
                "data": OfficerResponse.from_orm(officer).model_dump()
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    

@router.delete("/user/{user_id}")
def delete_officer(user_id: int, db=Depends(get_db)):
    try:
        officer = db.query(UserModel).filter(
            UserModel.user_id == user_id,
            UserModel.user_role.in_(OFFICER_ROLES)
        ).first()

        if not officer:
            raise HTTPException(status_code=404, detail="Officer not found")

        db.delete(officer)
        db.commit()

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "status_code": 200,
                "message": f"Officer with id {user_id} removed successfully",
                "data": None
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))