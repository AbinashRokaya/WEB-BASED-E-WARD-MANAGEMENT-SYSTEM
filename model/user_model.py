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
    password = Column(String(255),nullable=False)
    user_email = Column(String(150), unique=True, nullable=True)
    user_role = Column(Enum(RoleSchema), default=RoleSchema.Citizen)
    user_nepali_name = Column(String(150), nullable=True)
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
    death_registrations = relationship("DeathRegistrationModel", back_populates="submitted_by_user")
    migration_registrations=relationship("MigrationRegistrationModel",back_populates="submitted_by_user")

    ward=relationship("WardModel",back_populates="user")
    recommendation_letters = relationship("RecommendationLetterModel", back_populates="submitted_by_user")
    complaints = relationship(
    "ComplaintModel",
    back_populates="submitted_by_user",
    foreign_keys="ComplaintModel.complaint_submitted_by"
)

    assigned_complaints = relationship(
    "ComplaintModel",
    back_populates="assigned_user",
    foreign_keys="ComplaintModel.complaint_assigned_to"
)

    # ══════════════════════════════════════════════════════════
    # TAX MODULE — two kinds of relationship here:
    #   1. "I am the citizen this record is about" (citizen_id FK)
    #   2. "I am the officer who entered/updated/uploaded this"
    #      (entered_by / updated_by / uploaded_by / recorded_by FK)
    # Each pair needs foreign_keys= wherever a tax model has BOTH
    # a citizen_id and an entered_by pointing at users.user_id,
    # same reason complaints above needs it for submitted_by/assigned_to.
    # ══════════════════════════════════════════════════════════

    # Property tax — as the property owner, and as the officer who surveyed it
    property_records = relationship(
        "PropertyRecordModel",
        back_populates="citizen",
        foreign_keys="PropertyRecordModel.citizen_id",
    )
    property_records_entered = relationship(
        "PropertyRecordModel",
        back_populates="entered_by_user",
        foreign_keys="PropertyRecordModel.entered_by",
    )

    # Business tax — as the business owner, and as the officer who surveyed it
    business_records = relationship(
        "BusinessRecordModel",
        back_populates="citizen",
        foreign_keys="BusinessRecordModel.citizen_id",
    )
    business_records_entered = relationship(
        "BusinessRecordModel",
        back_populates="entered_by_user",
        foreign_keys="BusinessRecordModel.entered_by",
    )

    # Tax bills issued to this citizen
    tax_assessments = relationship("TaxAssessmentModel", back_populates="citizen")

    # Payments this user (usually a ward-office staff member) recorded on someone's behalf
    tax_payments_recorded = relationship("TaxPaymentModel", back_populates="recorded_by_user")

    # Disputes this citizen raised against their own assessment
    tax_disputes = relationship(
        "TaxDisputeModel",
        back_populates="citizen",
        foreign_keys="TaxDisputeModel.citizen_id",
    )

    # Ward Secretary: rate changes they made
    tax_rates_updated = relationship("WardTaxRateModel", back_populates="updated_by_user")

    # DVO: survey Excel batches they uploaded
    tax_import_batches = relationship("TaxImportBatchModel", back_populates="uploaded_by_user")


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
    password = Column(String(255),nullable=False)
    user_role = Column(Enum(RoleSchema), default=RoleSchema.Citizen)
    user_email = Column(String(150), unique=True, nullable=True)
    ward_id = Column(
        UUID(as_uuid=True),
        ForeignKey("ward.ward_id"),
        nullable=True
    )
    user_nepali_name = Column(String(150), nullable=True)
    user_nepali_name = Column(String(150), nullable=True)
    

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