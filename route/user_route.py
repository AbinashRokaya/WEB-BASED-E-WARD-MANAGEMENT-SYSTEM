from fastapi import HTTPException,Depends,APIRouter,Response
from fastapi.responses import JSONResponse
from database.db import get_db
from enum import Enum
from schema.user_schema import (UserRegisterationRequest, UserRegisterationResponse,OtpCodeRequest,OtpCodeResponse,
                                OtpVerificationRequest,Token,TokenData,TokenDataResponse)
from model.user_model import UserModel
from datetime import datetime
from datetime import timedelta
from model.user_model import OtpCode
import secrets
import os
from dotenv import load_dotenv
from twilio.rest import Client

from auth.jwt import create_access_token, verify_token  

load_dotenv()

TWILIO_ACCOUNT_SID = os.getenv("ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")

client=Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)


router = APIRouter(
    prefix="/v1/users",
    tags=["users"]
)


@router.post("/")
def create_user(request: UserRegisterationRequest, db: get_db = Depends()):
    try:
        existing_user = db.query(UserModel).filter(
            (UserModel.user_phone_number == request.user_phone_number) |
            (UserModel.user_citizenship_number == request.user_citizenship_number)
        ).first()

        if existing_user:
            raise HTTPException(status_code=400, detail="User with the same phone number or citizenship number already exists")

        new_user = UserModel(
            user_name=request.user_name,
            user_phone_number=request.user_phone_number,
            user_citizenship_number=request.user_citizenship_number,
            user_provience=request.user_provience,
            user_district=request.user_district,
            user_municipality=request.user_municipality,
            user_ward_number=request.user_ward_number
        )

        db.add(new_user)
        db.commit()
        db.refresh(new_user)

        new_user_response= UserRegisterationVerificationResponse(
            user_id=new_user.user_id,
            user_name=new_user.user_name,
            user_phone_number=new_user.user_phone_number,
            user_citizenship_number=new_user.user_citizenship_number,
            user_provience=new_user.user_provience,
            user_district=new_user.user_district,
            user_municipality=new_user.user_municipality,
            user_ward_number=new_user.user_ward_number
        )

        return JSONResponse(
                status_code=201,
                content={
                    "success": True,
                    "status_code": 201,
                    "message": "new user is created",
                    "data": new_user_response.model_dump()
                }
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500,detail=f"{e}")
    

@router.post("/")
def create_user(
    request: UserRegisterationRequest,
    db=Depends(get_db)
):
    existing_user = db.query(UserAccount).filter(
        (UserAccount.mobile_number == request.mobile_number) |
        (UserAccount.username == request.username)
    ).first()

    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="User already exists"
        )

    new_user = UserAccount(
        username=request.username,
        mobile_number=request.mobile_number,
        full_name=request.full_name,
        email=request.email
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return UserRegisterationResponse(
        user_id=new_user.user_id,
        username=new_user.username,
        mobile_number=new_user.mobile_number,
        full_name=new_user.full_name,
        email=new_user.email,
        is_active=new_user.is_active
    )
    
@router.post("/otp/verify")
def verify_otp(request: OtpVerificationRequest,response:Response, db: get_db = Depends()):
    try:
        otp_record = db.query(OtpCode).filter(
            OtpCode.otp_phone_number == request.otp_phone_number,
            OtpCode.otp_code == request.otp_code,
            OtpCode.is_used == False,
            OtpCode.expires_at > datetime.utcnow()
        ).first()

        if not otp_record:
            raise HTTPException(status_code=400, detail="Invalid or expired OTP code")

        otp_record.is_used = True
        db.commit()

        user=db.query(UserAccount).filter(UserAccount.mobile_number == request.otp_phone_number).first()

        if not user:
            raise HTTPException(status_code=400, detail="User not found")
        
        user_data=TokenData(
            user_id=user.user_id,
            user_name=user.user_name,
            user_phone_number=user.user_phone_number,
            user_citizenship_number=user.user_citizenship_number,
            user_provience=user.user_provience,
            user_district=user.user_district,
            user_municipality=user.user_municipality,
            user_ward_number=user.user_ward_number
        )
        access_token = create_access_token(data=user_data.model_dump())
        response.set_cookie(
    key="access_token",
    value=access_token,
    httponly=True,
    max_age=3600,
    samesite="none",
    secure=True,
    path="/",
)

        token_response=TokenDataResponse(
            user_details=user_data,
            access_token=access_token,
            
        )


        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "status_code": 200,
                "message": "OTP code verified successfully.",
                "data": token_response.model_dump()
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{e}")
    

@router.post("/verif/Citizen")
def verify_user_by_ward_computer(request:CitizenVerifyRequest, db: get_db = Depends()):
    try:
        user=db.query(UserVerifyModel).filter(
            UserVerifyModel.user_id==request.user_id,
            UserVerifyModel.user_phone_number==request.user_phone_number
        ).first()

        if not user:
            raise HTTPException(status_code=400, detail="User not found")
        
        user.user_status=request.user_status
        db.commit()
        if request.user_status=="approved":
            new_user=UserModel(
                user_id=user.user_id,
                user_name=user.user_name,
                user_phone_number=user.user_phone_number,
                user_citizenship_number=user.user_citizenship_number,
                user_provience=user.user_provience,
                user_district=user.user_district,
                user_municipality=user.user_municipality,
                user_ward_number=user.user_ward_number
            )
            db.add(new_user)
            db.commit()

            new_user_response= UserRegisterationResponse(
            user_id=new_user.user_id,
            user_name=new_user.user_name,
            user_phone_number=new_user.user_phone_number,
            user_citizenship_number=new_user.user_citizenship_number,
            user_provience=new_user.user_provience,
            user_district=new_user.user_district,
            user_municipality=new_user.user_municipality,
            user_ward_number=new_user.user_ward_number,
            
        )

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "status_code": 200,
                "message": f"New user is registered with status {request.user_status}",
                "data": new_user_response.model_dump() if request.user_status=="approved" else {"user_id":user.user_id,"user_status":user.user_status}
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{e}")
    

