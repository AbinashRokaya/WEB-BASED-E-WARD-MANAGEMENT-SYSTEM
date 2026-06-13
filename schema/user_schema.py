try:
    # pydantic v2
    from pydantic import BaseModel, field_validator
except Exception:
    # pydantic v1 fallback
    from pydantic import BaseModel
    from pydantic import validator as field_validator
import re
from enum import Enum
from typing import List,Literal


provience_list=["Koshi","Madhesh","Bagmati","Gandaki","Lumbini","Karnali","Sudurpashchim"]
class RegistrationStatus(str,Enum):
    Pending="pending"
    Approved="approved"
    Rejected="rejected"
class UserRegisterationRequest(BaseModel):
    user_name: str 
    user_phone_number: str
    user_citizenship_number: str
    user_provience: str
    user_district: str
    user_municipality: str
    user_ward_number: int

    @field_validator("user_phone_number")
    def validate_phone_number(cls, value):
        if not re.fullmatch(r'^(98|97)\d{8}$', value):
                raise ValueError(
                    "Phone number must be a valid Nepali mobile number"
                )
        return value
    
    @field_validator("user_ward_number")
    def validate_ward_number(cls, value):
        if value < 1 or value > 32:
            raise ValueError("Ward number must be between 1 and 32")
        return value
    
    @field_validator("user_provience")
    def validate_provience(cls, value):
        if value not in provience_list:
            raise ValueError(f"Provience must be one of the following: {', '.join(provience_list)}")
        return value

class UserRegisterationVerificationResponse(BaseModel):
    user_id: int
    user_name: str 
    user_phone_number: str
    user_citizenship_number: str
    user_provience: str
    user_district: str
    user_municipality: str
    user_ward_number: int
    user_status: RegistrationStatus

class UserRegisterationResponse(BaseModel):
    user_id: int
    user_name: str 
    user_phone_number: str
    user_citizenship_number: str
    user_provience: str
    user_district: str
    user_municipality: str
    user_ward_number: int
   

class OtpCodeRequest(BaseModel):
    otp_phone_number: str

    @field_validator("otp_phone_number")
    def validate_phone_number(cls, value):
        if not re.fullmatch(r'^(98|97)\d{8}$', value):
                raise ValueError(
                    "Phone number must be a valid Nepali mobile number"
                )
        return value
    
class OtpCodeResponse(BaseModel):
    otp_phone_number: str
    is_used: bool
    expires_at: str

class OtpVerificationRequest(BaseModel):
    otp_phone_number: str
    otp_code: str

    @field_validator("otp_phone_number")
    def validate_phone_number(cls, value):
        if not re.fullmatch(r'^(98|97)\d{8}$', value):
                raise ValueError(
                    "Phone number must be a valid Nepali mobile number"
                )
        return value
    
    @field_validator("otp_code")
    def validate_otp_code(cls, value):
        if not re.fullmatch(r'^\d{6}$', value):
            raise ValueError("OTP code must be a 6-digit number")
        return value

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    user_id: int
    user_name: str 
    user_phone_number: str
    user_citizenship_number: str
    user_provience: str
    user_district: str
    user_municipality: str
    user_ward_number: int

class TokenDataResponse(BaseModel):
    user_details: TokenData
    access_token: str


class RoleSchema(str,Enum):
    SuperAdmin="superadmin"
    Citizen="citizen"
    WardChairperson="wardchairperson"
    WardSecretary="wardsecretary"
    DataValidationOfficer="datavalidationofficer"

Permission_Role={
     RoleSchema.SuperAdmin:{"create_user", "read_user", "update_user", "delete_user"},
     RoleSchema.Citizen:{"read_user","write_form"},
     RoleSchema.WardChairperson:{"create_user", "read_user", "update_user"},
     RoleSchema.WardSecretary:{"create_user", "read_user", "update_user"},
     RoleSchema.DataValidationOfficer:{"read_user","validate_data"}
}
Action=Literal["create_user", "read_user", "update_user", "delete_user", "write_form", "validate_data"]


class CitizenVerifyRequest(BaseModel):
     user_id:int
     user_phone_number:str
     user_status:RegistrationStatus