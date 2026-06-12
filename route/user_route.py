from fastapi import HTTPException,Depends,APIRouter
from fastapi.responses import JSONResponse
from database.db import get_db
from enum import Enum
from schema.user_schema import (UserRegisterationRequest, UserRegisterationResponse,OtpCodeRequest,OtpCodeResponse,
                                OtpVerificationRequest,Token,TokenData,TokenDataResponse)
from model.user_model import UserAccount, OtpCode
from datetime import datetime, timedelta
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
    prefix="/users",
    tags=["users"]
)


@router.post("/")
def create_user(request: UserRegisterationRequest, db: get_db = Depends()):
    try:
        existing_user = db.query(UserAccount).filter(
            (UserAccount.mobile_number == request.user_phone_number) |
            (UserAccount.username == request.user_name)
        ).first()

        if existing_user:
            raise HTTPException(status_code=400, detail="User with the same phone number or citizenship number already exists")

        new_user = UserAccount(
            username=request.user_name,
            mobile_number=request.user_phone_number,
            full_name=request.user_name,
            email=None
        )

        db.add(new_user)
        db.commit()
        db.refresh(new_user)

        new_user_response= UserRegisterationResponse(
            user_id=new_user.user_id,
            user_name=new_user.full_name,
            user_phone_number=new_user.mobile_number,
            user_citizenship_number="",
            user_provience="",
            user_district="",
            user_municipality="",
            user_ward_number=""
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
def verify_otp(request: OtpVerificationRequest, db: get_db = Depends()):
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
    

