from sqlalchemy import Column, Integer, String,Boolean, DateTime,func,Enum,ForeignKey
from database.db import Base
from schema.user_schema import RoleSchema, RegistrationStatus
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID

class UserModel(Base):
    __tablename__ = "users"

    user_id = Column(Integer, primary_key=True, index=True)
    user_name = Column(String, unique=True, index=True)
    user_phone_number = Column(String, unique=True, index=True)
    user_citizenship_number = Column(String, unique=True, index=True)
    user_provience = Column(String)
    user_district = Column(String)
    user_municipality = Column(String)
    user_ward_number = Column(Integer)
    user_role = Column(Enum(RoleSchema), default=RoleSchema.Citizen)
    ward_id = Column(
        UUID(as_uuid=True),
        ForeignKey("ward.ward_id"),
        nullable=True
    )

    reated_at = Column(
        DateTime,
        server_default=func.now()
    )

    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now()
    )
    birth_registrations = relationship("BirthRegistrationModel", back_populates="submitted_by_user")
    ward=relationship("WardModel",back_populates="user")



    


class OtpCode(Base):
    __tablename__ = "otp_codes"

    otp_id = Column(Integer, primary_key=True, index=True)

    otp_phone_number = Column(String(15), nullable=False)

    otp_code = Column(String(6), nullable=False)

    is_used = Column(Boolean, default=False)

    expires_at = Column(DateTime, nullable=False)

    created_at = Column(
        DateTime,
        server_default=func.now()
    )

    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now()
    )

   




class UserVerifyModel(Base):
    __tablename__ = "users_verify"

    user_id = Column(Integer, primary_key=True, index=True)
    user_name = Column(String, unique=True, index=True)
    user_phone_number = Column(String, unique=True, index=True)
    user_citizenship_number = Column(String, unique=True, index=True)
    user_provience = Column(String)
    user_district = Column(String)
    user_municipality = Column(String)
    user_ward_number = Column(Integer)
    user_role = Column(Enum(RoleSchema), default=RoleSchema.Citizen)
    ward_id = Column(
        UUID(as_uuid=True),
        ForeignKey("ward.ward_id"),
        nullable=True
    )

    user_status = Column(Enum(RegistrationStatus), default=RegistrationStatus.Pending)

    reated_at = Column(
        DateTime,
        server_default=func.now()
    )

    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now()
    )

    wardVerify=relationship("WardModel",back_populates="userVerify")








    