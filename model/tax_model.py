import uuid
from sqlalchemy import (
    Column, String, Integer, Boolean, Text, Numeric, ForeignKey,
    DateTime, JSON, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy import Enum as SAEnum
from sqlalchemy.sql import func
from database.db import Base
from enums.tax_enums import (
    TaxType, PropertyType, ConstructionType, LocationZone, BusinessScaleTier,
    RentalUnitType, TaxRecordStatus, ImportBatchStatus, ImportRowMatchStatus,
    ImportRowAction, TaxImportRowStatus, TaxAssessmentStatus, TaxPaymentMethod,
    TaxDisputeStatus,
)


# ══════════════════════════════════════════════════════════════
# WARD-CONFIGURABLE RATES — Ward Secretary edits these per ward.
# effective_from + fiscal_year keep history: changing a rate never
# rewrites tax already assessed under the old rate.
# ══════════════════════════════════════════════════════════════
class WardTaxRateModel(Base):
    __tablename__ = "ward_tax_rate"

    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ward_id       = Column(UUID(as_uuid=True), ForeignKey("ward.ward_id", ondelete="CASCADE"), nullable=False)
    tax_type      = Column(SAEnum(TaxType), nullable=False)

    property_type      = Column(SAEnum(PropertyType), nullable=True)
    construction_type   = Column(SAEnum(ConstructionType), nullable=True)
    location_zone       = Column(SAEnum(LocationZone), nullable=True)
    business_scale_tier = Column(SAEnum(BusinessScaleTier), nullable=True)

    rate_value      = Column(Numeric(10, 4), nullable=False)
    fiscal_year     = Column(String(10), nullable=False)
    effective_from  = Column(DateTime, server_default=func.now(), nullable=False)

    updated_by = Column(Integer, ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    ward = relationship("WardModel", back_populates="tax_rates")
    updated_by_user = relationship("UserModel", back_populates="tax_rates_updated")


# ══════════════════════════════════════════════════════════════
# PROPERTY / BUSINESS / RENTAL
# ══════════════════════════════════════════════════════════════
class PropertyRecordModel(Base):
    __tablename__ = "property_record"

    id               = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    citizen_id       = Column(Integer, ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True)
    ward_id          = Column(UUID(as_uuid=True), ForeignKey("ward.ward_id"), nullable=False)

    lalpurja_number  = Column(String(100), nullable=True, unique=True)

    land_area_sqm      = Column(Numeric(10, 2), nullable=False)
    built_up_area_sqm  = Column(Numeric(10, 2), nullable=True)
    property_type      = Column(SAEnum(PropertyType), nullable=False)
    construction_type   = Column(SAEnum(ConstructionType), nullable=True)
    location_zone       = Column(SAEnum(LocationZone), nullable=False, default=LocationZone.INTERIOR)
    number_of_floors    = Column(Integer, nullable=True)

    entered_by     = Column(Integer, ForeignKey("users.user_id", ondelete="SET NULL"), nullable=False)
    survey_date    = Column(DateTime, nullable=False, server_default=func.now())
    import_batch_id = Column(UUID(as_uuid=True), ForeignKey("tax_import_batch.id", ondelete="SET NULL"), nullable=True)

    status       = Column(SAEnum(TaxRecordStatus), nullable=False, default=TaxRecordStatus.ASSESSED)
    dispute_note = Column(Text, nullable=True)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    citizen      = relationship("UserModel", foreign_keys=[citizen_id], back_populates="property_records")
    entered_by_user = relationship("UserModel", foreign_keys=[entered_by], back_populates="property_records_entered")
    ward         = relationship("WardModel", back_populates="property_records")
    rental_units = relationship("RentalUnitModel", back_populates="property")


class BusinessCategoryModel(Base):
    __tablename__ = "business_category"

    id       = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name     = Column(String(150), nullable=False, unique=True)
    base_fee = Column(Numeric(10, 2), nullable=False, default=0)

    created_at = Column(DateTime, server_default=func.now())

    business_records = relationship("BusinessRecordModel", back_populates="category")


class BusinessRecordModel(Base):
    __tablename__ = "business_record"

    id           = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    citizen_id   = Column(Integer, ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True)
    ward_id      = Column(UUID(as_uuid=True), ForeignKey("ward.ward_id"), nullable=False)

    business_name       = Column(String(200), nullable=False)
    category_id         = Column(UUID(as_uuid=True), ForeignKey("business_category.id"), nullable=False)
    scale_tier          = Column(SAEnum(BusinessScaleTier), nullable=False, default=BusinessScaleTier.SMALL)
    registration_number = Column(String(100), nullable=True, unique=True)

    entered_by      = Column(Integer, ForeignKey("users.user_id", ondelete="SET NULL"), nullable=False)
    survey_date     = Column(DateTime, nullable=False, server_default=func.now())
    import_batch_id = Column(UUID(as_uuid=True), ForeignKey("tax_import_batch.id", ondelete="SET NULL"), nullable=True)

    status       = Column(SAEnum(TaxRecordStatus), nullable=False, default=TaxRecordStatus.ASSESSED)
    dispute_note = Column(Text, nullable=True)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    citizen         = relationship("UserModel", foreign_keys=[citizen_id], back_populates="business_records")
    entered_by_user = relationship("UserModel", foreign_keys=[entered_by], back_populates="business_records_entered")
    ward            = relationship("WardModel", back_populates="business_records")
    category        = relationship("BusinessCategoryModel", back_populates="business_records")


class RentalUnitModel(Base):
    __tablename__ = "rental_unit"

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    property_id = Column(UUID(as_uuid=True), ForeignKey("property_record.id", ondelete="CASCADE"), nullable=False)

    unit_type         = Column(SAEnum(RentalUnitType), nullable=False)
    number_of_rooms   = Column(Integer, nullable=True)
    monthly_rent      = Column(Numeric(10, 2), nullable=False)
    is_active         = Column(Boolean, nullable=False, default=True)

    entered_by  = Column(Integer, ForeignKey("users.user_id", ondelete="SET NULL"), nullable=False)
    survey_date = Column(DateTime, nullable=False, server_default=func.now())

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    property = relationship("PropertyRecordModel", back_populates="rental_units")


# ══════════════════════════════════════════════════════════════
# EXCEL IMPORT PIPELINE
# ══════════════════════════════════════════════════════════════
class TaxImportBatchModel(Base):
    __tablename__ = "tax_import_batch"

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ward_id     = Column(UUID(as_uuid=True), ForeignKey("ward.ward_id"), nullable=False)
    tax_type    = Column(SAEnum(TaxType), nullable=False)
    filename    = Column(String(255), nullable=False)
    uploaded_by = Column(Integer, ForeignKey("users.user_id", ondelete="SET NULL"), nullable=False)
    status      = Column(SAEnum(ImportBatchStatus), nullable=False, default=ImportBatchStatus.PROCESSING)

    uploaded_at  = Column(DateTime, server_default=func.now())
    committed_at = Column(DateTime, nullable=True)

    ward         = relationship("WardModel")
    uploaded_by_user = relationship("UserModel", back_populates="tax_import_batches")
    rows         = relationship("TaxImportRowModel", back_populates="batch", cascade="all, delete-orphan")


class TaxImportRowModel(Base):
    __tablename__ = "tax_import_row"

    id       = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    batch_id = Column(UUID(as_uuid=True), ForeignKey("tax_import_batch.id", ondelete="CASCADE"), nullable=False)
    row_number = Column(Integer, nullable=False)

    raw_data = Column(JSON, nullable=False)
    phone_number = Column(String(20), nullable=True)

    matched_citizen_id  = Column(Integer, ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True)
    matched_property_id = Column(UUID(as_uuid=True), ForeignKey("property_record.id", ondelete="SET NULL"), nullable=True)

    match_status  = Column(SAEnum(ImportRowMatchStatus), nullable=False)
    import_action = Column(SAEnum(ImportRowAction), nullable=True)
    error_message = Column(Text, nullable=True)

    status = Column(SAEnum(TaxImportRowStatus), nullable=False, default=TaxImportRowStatus.PENDING)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    batch            = relationship("TaxImportBatchModel", back_populates="rows")
    matched_citizen  = relationship("UserModel", foreign_keys=[matched_citizen_id])
    matched_property = relationship("PropertyRecordModel", foreign_keys=[matched_property_id])

    @property
    def matched_citizen_name(self):
        if self.matched_citizen:
            return self.matched_citizen.user_nepali_name or self.matched_citizen.user_name
        return None


# ══════════════════════════════════════════════════════════════
# ASSESSMENT / PAYMENT / RECEIPT / DISPUTE
# ══════════════════════════════════════════════════════════════
class TaxAssessmentModel(Base):
    __tablename__ = "tax_assessment"

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    record_id   = Column(UUID(as_uuid=True), nullable=False, index=True)
    tax_type    = Column(SAEnum(TaxType), nullable=False)
    citizen_id  = Column(Integer, ForeignKey("users.user_id", ondelete="SET NULL"), nullable=False)
    ward_id     = Column(UUID(as_uuid=True), ForeignKey("ward.ward_id"), nullable=False)

    fiscal_year   = Column(String(10), nullable=False)
    base_amount   = Column(Numeric(12, 2), nullable=False)
    penalty_amount = Column(Numeric(12, 2), nullable=False, default=0)
    discount_amount = Column(Numeric(12, 2), nullable=False, default=0)
    total_due     = Column(Numeric(12, 2), nullable=False)

    due_date = Column(DateTime, nullable=False)
    status   = Column(SAEnum(TaxAssessmentStatus), nullable=False, default=TaxAssessmentStatus.ASSESSED)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("record_id", "tax_type", "fiscal_year", name="uq_assessment_record_year"),
    )

    citizen  = relationship("UserModel", back_populates="tax_assessments")
    ward     = relationship("WardModel")
    payments = relationship("TaxPaymentModel", back_populates="assessment")
    disputes = relationship("TaxDisputeModel", back_populates="assessment")

    @property
    def citizen_name(self):
        if self.citizen:
            return self.citizen.user_nepali_name or self.citizen.user_name
        return None

    @property
    def receipt(self):
        """
        The payment that actually settled this assessment, if any — used
        by TaxAssessmentResponse.receipt so the frontend can show a
        "Download Receipt" link straight off /assessments/my without a
        second round-trip. An assessment can have more than one
        TaxPaymentModel row (e.g. an abandoned/failed Khalti attempt
        followed by a successful one), so this picks the one that
        actually covered total_due and — for KHALTI — was confirmed
        Completed by the gateway, same rule the backfill script uses.
        """
        candidates = [
            p for p in self.payments
            if p.amount_paid is not None and p.amount_paid >= self.total_due
            and (p.method != TaxPaymentMethod.KHALTI or p.gateway_status == "Completed")
        ]
        if not candidates:
            return None
        return sorted(candidates, key=lambda p: p.paid_at or 0)[-1]


class TaxPaymentModel(Base):
    __tablename__ = "tax_payment"

    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    assessment_id = Column(UUID(as_uuid=True), ForeignKey("tax_assessment.id", ondelete="CASCADE"), nullable=False)
    amount_paid   = Column(Numeric(12, 2), nullable=False)
    method        = Column(SAEnum(TaxPaymentMethod), nullable=False)
    receipt_no    = Column(String(100), nullable=False, unique=True)
    paid_at       = Column(DateTime, server_default=func.now())
    recorded_by   = Column(Integer, ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True)

    # Khalti gateway tracking — only populated for method=KHALTI.
    pidx            = Column(String(100), nullable=True, unique=True)
    gateway_status  = Column(String(50), nullable=True)
    transaction_id  = Column(String(100), nullable=True)

    assessment = relationship("TaxAssessmentModel", back_populates="payments")
    recorded_by_user = relationship("UserModel", back_populates="tax_payments_recorded")

    # The actual PDF/QR/hash artifact lives in its own table now — see
    # TaxReceiptModel below, same split as BirthRegistrationModel /
    # CertificateModel. `cascade="all, delete-orphan"` since a receipt
    # never outlives the payment it belongs to.
    receipt = relationship(
        "TaxReceiptModel",
        back_populates="payment",
        uselist=False,
        cascade="all, delete-orphan",
    )

    # ── Backward-compatible read-only accessors ──────────────────────
    # Everything upstream (TaxPaymentResponse, the tax router, the
    # frontend) was written against payment.pdf_path / payment.qr_path /
    # payment.data_hash / payment.receipt_issued_at directly, from back
    # when those columns lived on this table. Rather than touch every
    # call site, these properties transparently proxy through to the
    # new TaxReceiptModel row so existing code keeps working unchanged.
    # New code should prefer `payment.receipt.<field>` directly.
    @property
    def pdf_path(self):
        return self.receipt.pdf_path if self.receipt else None

    @property
    def qr_path(self):
        return self.receipt.qr_path if self.receipt else None

    @property
    def data_hash(self):
        return self.receipt.data_hash if self.receipt else None

    @property
    def receipt_issued_at(self):
        return self.receipt.issued_at if self.receipt else None


class TaxReceiptModel(Base):
    """
    The issued receipt artifact for a completed tax payment — mirrors
    CertificateModel's split from BirthRegistrationModel: the payment
    (like a registration) is the record of what happened, and the
    receipt (like a certificate) is the separately-issued proof document
    with its own hash/QR/PDF and its own validity/revocation state.

    One-to-one with TaxPaymentModel: a payment either has no receipt yet
    (still being generated / generation failed) or exactly one — same
    idempotency guarantee issue_tax_receipt() already enforced, now
    backed by payment_id being unique instead of a payment.pdf_path
    NULL-check.
    """
    __tablename__ = "tax_receipt"

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    payment_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tax_payment.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    data_hash      = Column(String(64), nullable=False)
    qr_path        = Column(String(255), nullable=True)
    pdf_path       = Column(String(255), nullable=True)
    is_valid       = Column(Boolean, nullable=False, default=True)
    revoked_reason = Column(Text, nullable=True)
    issued_by      = Column(Integer, ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True)
    issued_at      = Column(DateTime, server_default=func.now())

    payment = relationship("TaxPaymentModel", back_populates="receipt", uselist=False)


class TaxDisputeModel(Base):
    __tablename__ = "tax_dispute"

    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    assessment_id = Column(UUID(as_uuid=True), ForeignKey("tax_assessment.id", ondelete="CASCADE"), nullable=False)
    citizen_id    = Column(Integer, ForeignKey("users.user_id", ondelete="SET NULL"), nullable=False)
    reason        = Column(Text, nullable=False)
    status        = Column(SAEnum(TaxDisputeStatus), nullable=False, default=TaxDisputeStatus.PENDING)
    resolved_by   = Column(Integer, ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True)
    resolution_note = Column(Text, nullable=True)

    created_at  = Column(DateTime, server_default=func.now())
    resolved_at = Column(DateTime, nullable=True)

    assessment = relationship("TaxAssessmentModel", back_populates="disputes")
    citizen    = relationship("UserModel", foreign_keys=[citizen_id], back_populates="tax_disputes")