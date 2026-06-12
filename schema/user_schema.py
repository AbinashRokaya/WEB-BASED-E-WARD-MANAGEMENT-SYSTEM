from pydantic import BaseModel, field_validator
from uuid import UUID
from typing import Optional
import re
from enum import Enum
from typing import Literal


class UserRegisterationRequest(BaseModel):
    username: str
    mobile_number: str
    full_name: str
    email: Optional[str] = None

    @field_validator("mobile_number")
    @classmethod
    def validate_phone_number(cls, value):
        if not re.fullmatch(r'^(98|97)\d{8}$', value):
            raise ValueError(
                "Phone number must be a valid Nepali mobile number"
            )
        return value


class UserRegisterationResponse(BaseModel):
    user_id: UUID
    username: str
    mobile_number: str
    full_name: str
    email: Optional[str] = None
    is_active: bool


class OtpCodeRequest(BaseModel):
    otp_phone_number: str

    @field_validator("otp_phone_number")
    @classmethod
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
    @classmethod
    def validate_phone_number(cls, value):
        if not re.fullmatch(r'^(98|97)\d{8}$', value):
            raise ValueError(
                "Phone number must be a valid Nepali mobile number"
            )
        return value

    @field_validator("otp_code")
    @classmethod
    def validate_otp_code(cls, value):
        if not re.fullmatch(r'^\d{6}$', value):
            raise ValueError("OTP code must be a 6-digit number")
        return value


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    user_id: UUID
    username: str
    mobile_number: str
    full_name: str
    email: Optional[str] = None


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

