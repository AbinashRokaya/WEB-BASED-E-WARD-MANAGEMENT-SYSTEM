from pydantic import BaseModel,field_validator,EmailStr,ConfigDict
from typing import Optional
from typing import Optional
from schema.birth_registration_schema import NEPALI_REGEX
from schema.user_schema import RoleSchema
from uuid import UUID
from typing import List
provience_list=["Koshi","Madhesh","Bagmati","Gandaki","Lumbini","Karnali","Sudurpashchim"]

class CreateWordRequest(BaseModel):

   
    ward_name:str
    ward_no:int 
    ward_municipality:str 
    ward_district:str 
    ward_province:str 
    ward_contact_number:str 
    ward_email:EmailStr
    ward_nepali_name:str
    ward_nepali_municipality:str
    ward_nepali_district:str
    ward_nepali_province:str
   

    @field_validator(
        "ward_nepali_name",
        "ward_nepali_municipality",
        "ward_nepali_district",
        "ward_nepali_province",
        mode="before"
    )
    @classmethod
    def validate_nepali_name(cls, value):
        if value is None:
            return value

        value = value.strip()

        if not NEPALI_REGEX.fullmatch(value):
            raise ValueError("Name must contain only Nepali (Devanagari) characters.")

        return value

    @field_validator("ward_province")
    def validate_province(cls, value):
        if value not in provience_list:
            raise ValueError(f"Provience must be one of the following: {', '.join(provience_list)}")
        return value



class CreateWordResponse(BaseModel):
    ward_id:UUID
    ward_name:str
    ward_no:int 
    ward_municipality:str 
    ward_district:str 
    ward_province:str 
    ward_contact_number:str 
    ward_email:EmailStr

class GetAllWardResponse(BaseModel):
    ward_list:List[CreateWordResponse]
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
    password:str

# class OfficerResponse(BaseModel):
#     user_id: int
#     user_full_name: str
#     user_email: EmailStr
#     user_phone_number: str
#     user_role: str

#     model_config = ConfigDict(from_attributes=True)
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

    model_config = ConfigDict(from_attributes=True)