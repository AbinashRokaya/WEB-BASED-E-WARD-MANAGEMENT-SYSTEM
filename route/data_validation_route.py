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
    UpdateParentRequest, UpdateNomineeRequest, UpdateAddressRequest,AddressResponse,BirthRegistrationResponseAll

)
from auth.current_user import require_permission

router = APIRouter(
    prefix="/v1/data-validation",
    tags=["Data Validation"]
)


