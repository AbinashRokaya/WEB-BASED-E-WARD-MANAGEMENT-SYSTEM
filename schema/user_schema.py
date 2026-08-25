import re
from enum import Enum
from typing import List, Literal, Optional
from uuid import UUID

# Robust Pydantic v1 and v2 cross-compatibility setup
try:
    # Pydantic v2
    from pydantic import BaseModel, field_validator, ConfigDict
    HAS_V2 = True
except ImportError:
    # Pydantic v1 fallback
    from pydantic import BaseModel, validator as field_validator
    HAS_V2 = False

provience_list = ["Koshi", "Madhesh", "Bagmati", "Gandaki", "Lumbini", "Karnali", "Sudurpashchim"]
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
    password: str
    user_email:str
    user_nepali_name:str

    @field_validator("user_email")
    def validate_email(cls, value):
        if not re.fullmatch(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', value):
            raise ValueError("Invalid email address")
        return value

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
    user_email:str
    user_nepali_name:str
   

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

class LoginRequest(BaseModel):
    user_phone_number: str
    password: str

    @field_validator("user_phone_number")
    def validate_phone_number(cls, value):
        if not re.fullmatch(r'^(98|97)\d{8}$', value):
                raise ValueError(
                    "Phone number must be a valid Nepali mobile number"
                )
        return value
class TokenData(BaseModel):
    user_id: int
    user_name: str 
    user_phone_number: str
    user_citizenship_number: str
    user_provience: str
    user_district: str
    user_role:str
    user_municipality: str
    user_ward_number: int
    user_ward_id:UUID| None = None

class TokenDataResponse(BaseModel):
    user_details: TokenData
    access_token: str


class RoleSchema(str,Enum):
    SuperAdmin="superadmin"
    Citizen="citizen"
    WardChairperson="wardchairperson"
    WardSecretary="wardsecretary"
    DataValidationOfficer="datavalidationofficer"

# ══════════════════════════════════════════════════════════════════
# PERMISSION MATRIX
# ══════════════════════════════════════════════════════════════════
#
# BUG FIXED HERE: "issue_certificate" was used by SIX endpoints
# (birth/death/migration/recommendation issue-certificate) but was never
# listed in Action or granted to ANY role. require_permission() does
#     allowed = Permission_Role.get(role_enum, set())
#     if action not in allowed: raise 403
# so every one of those endpoints returned 403 for every role, including
# the Ward Chairperson. That is why the working flow went through
# /approve with "update_user" instead — the intended endpoints were dead.
#
# Ward Secretary also gets issue_certificate: death_certificate_service
# signs with "secretary OR chairperson", unlike birth/recommendation
# which are chairperson-only.
#
# The document pipeline and who owns each step:
#
#   SUBMITTED --(DataValidationOfficer: validate_data)--> APPROVED
#   APPROVED  --(WardSecretary:        update_user)-----> VERIFIED
#   VERIFIED  --(WardChairperson:      issue_certificate)-> CERTIFICATE_ISSUED
#
Permission_Role = {
    RoleSchema.SuperAdmin: {
        "create_user", "read_user", "update_user", "delete_user",
        "write_form", "validate_data", "issue_certificate",
        "update_registration",
    },
    RoleSchema.Citizen: {
        # A citizen uploads supporting documents to their OWN registration,
        # which is what update_registration guards. Ownership itself is
        # checked inside the endpoint; this only gates the action.
        "read_user", "write_form", "update_registration",
    },
    RoleSchema.WardChairperson: {
        "create_user", "read_user", "update_user", "issue_certificate",
        "update_registration",
    },
    RoleSchema.WardSecretary: {
        "create_user", "read_user", "update_user", "issue_certificate",
        "update_registration",
    },
    RoleSchema.DataValidationOfficer: {
        "read_user", "validate_data", "update_registration","update_user"
    },
}

Action = Literal[
    "create_user",
    "read_user",
    "update_user",
    "delete_user",
    "write_form",
    "validate_data",
    "issue_certificate",     # was missing — see note above
    "update_registration",   # also missing: used by birth upload-documents
]


class CitizenVerifyRequest(BaseModel):
     user_id:int
     user_phone_number:str
     user_status:RegistrationStatus
     


class UserResponse(BaseModel):
    user_id: int
    user_name: str
    user_phone_number: str
    user_citizenship_number: str
    user_provience: str
    user_district: str
    user_municipality: str
    user_ward_number: int
    user_role: RoleSchema
    ward_id:UUID
    user_status:RegistrationStatus

    model_config = ConfigDict(from_attributes=True)

class ListUserResponse(BaseModel):
    user_list:List[UserResponse]