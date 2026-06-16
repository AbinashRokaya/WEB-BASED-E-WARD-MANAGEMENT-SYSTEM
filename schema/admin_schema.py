from pydantic import BaseModel,field_validator,EmailStr
from typing import Optional
from typing import Optional
from schema.user_schema import RoleSchema

provience_list=["Koshi","Madhesh","Bagmati","Gandaki","Lumbini","Karnali","Sudurpashchim"]

class CreateWordRequest(BaseModel):

   
    ward_name:str
    ward_no:int 
    ward_municipality:str 
    ward_district:str 
    ward_province:str 
    ward_contact_number:str 
    ward_email:EmailStr

    @field_validator("ward_province")
    def validate_province(cls, value):
        if value not in provience_list:
            raise ValueError(f"Provience must be one of the following: {', '.join(provience_list)}")
        return value



class CreateWordResponse(BaseModel):
    ward_id:str
    ward_name:str
    ward_no:int 
    ward_municipality:str 
    ward_district:str 
    ward_provience:str 
    ward_contact_number:str 
    ward_email:EmailStr

class UpdateWardRequest(BaseModel):
    ward_no: Optional[int] = None
    ward_name: Optional[str] = None
    ward_municipality: Optional[str] = None
    ward_district: Optional[str] = None
    ward_province: Optional[str] = None
    ward_contact_number: Optional[str] = None
    ward_email: Optional[EmailStr] = None


class AssignOfficerRequest(BaseModel):
    user_name: str
    user_phone_number: str
    user_citizenship_number: str
    user_province: str
    user_district: str
    user_municipality: str
    user_ward_number: int
    user_role: RoleSchema


class UpdateOfficerRequest(BaseModel):
    user_name: Optional[str] = None
    user_phone_number: Optional[str] = None
    user_citizenship_number: Optional[str] = None
    user_province: Optional[str] = None
    user_district: Optional[str] = None
    user_municipality: Optional[str] = None
    user_ward_number: Optional[int] = None
    user_role: Optional[RoleSchema] = None


class OfficerResponse(BaseModel):
    user_id: int
    user_name: str
    user_phone_number: str
    user_citizenship_number: str
    user_province: str
    user_district: str
    user_municipality: str
    user_ward_number: int
    user_role: RoleSchema

    class Config:
        from_attributes = True