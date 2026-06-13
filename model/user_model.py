from sqlalchemy import Column, Integer, String,Boolean, DateTime,func,Enum
from database.db import Base
from schema.user_schema import RoleSchema, RegistrationStatus

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

    reated_at = Column(
        DateTime,
        server_default=func.now()
    )

    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now()
    )


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







    