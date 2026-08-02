# ══════════════════════════════════════════════════════════════
# Add these to model/enums.py (same file as BirthRegistrationStatus,
# GenderType, etc.) — kept in a separate file here only so the tax
# module's enums are easy to review before you paste them in.
# ══════════════════════════════════════════════════════════════
import enum


class TaxType(str, enum.Enum):
    PROPERTY   = "PROPERTY"
    HOUSE_RENT = "HOUSE_RENT"
    BUSINESS   = "BUSINESS"


class PropertyType(str, enum.Enum):
    RESIDENTIAL   = "RESIDENTIAL"
    COMMERCIAL    = "COMMERCIAL"
    INSTITUTIONAL = "INSTITUTIONAL"
    AGRICULTURAL  = "AGRICULTURAL"
    INDUSTRIAL    = "INDUSTRIAL"


class ConstructionType(str, enum.Enum):
    RCC          = "RCC"
    SEMI_PUCCA   = "SEMI_PUCCA"
    MUD_BONDED   = "MUD_BONDED"
    TIN_ROOF     = "TIN_ROOF"


class LocationZone(str, enum.Enum):
    MAIN_ROAD = "MAIN_ROAD"
    SUB_ROAD  = "SUB_ROAD"
    INTERIOR  = "INTERIOR"


class BusinessScaleTier(str, enum.Enum):
    SMALL  = "SMALL"
    MEDIUM = "MEDIUM"
    LARGE  = "LARGE"


class RentalUnitType(str, enum.Enum):
    SINGLE_ROOM = "SINGLE_ROOM"
    FLAT        = "FLAT"
    SHOP        = "SHOP"
    FULL_HOUSE  = "FULL_HOUSE"
    FLOOR       = "FLOOR"


# ── Record status — who put the data in and has it been reviewed ──
class TaxRecordStatus(str, enum.Enum):
    ASSESSED  = "ASSESSED"   # entered by survey/DVO, tax can be generated
    DISPUTED  = "DISPUTED"   # citizen raised a correction request
    CORRECTED = "CORRECTED"  # officer reviewed the dispute and updated it


# ── Excel import pipeline ──
class ImportBatchStatus(str, enum.Enum):
    PROCESSING = "PROCESSING"  # file being parsed/matched
    REVIEW     = "REVIEW"      # ready for DVO to review rows
    COMMITTED  = "COMMITTED"   # approved rows pushed into live tables


class ImportRowMatchStatus(str, enum.Enum):
    MATCHED           = "MATCHED"            # phone found, single record, same ward
    NOT_REGISTERED    = "NOT_REGISTERED"     # phone not found — citizen must register first
    WARD_MISMATCH     = "WARD_MISMATCH"      # phone belongs to a citizen registered under a DIFFERENT ward
    DUPLICATE_IN_BATCH = "DUPLICATE_IN_BATCH"  # same phone appears twice in this file
    INVALID_DATA      = "INVALID_DATA"       # required field missing / bad type


class ImportRowAction(str, enum.Enum):
    NEW          = "NEW"           # no existing record with this lalpurja/reg no — will insert
    UPDATE       = "UPDATE"        # matches an existing property/business — will update
    NEEDS_REVIEW = "NEEDS_REVIEW"  # ambiguous match, DVO must confirm


class TaxImportRowStatus(str, enum.Enum):
    PENDING  = "PENDING"   # awaiting DVO decision
    APPROVED = "APPROVED"  # DVO approved — will be committed
    EDITED   = "EDITED"    # DVO corrected a field before approving
    REJECTED = "REJECTED"  # DVO threw the row out


# ── Assessment / payment ──
class TaxAssessmentStatus(str, enum.Enum):
    ASSESSED = "ASSESSED"
    PAID     = "PAID"
    OVERDUE  = "OVERDUE"
    DISPUTED = "DISPUTED"


class TaxPaymentMethod(str, enum.Enum):
    CASH      = "CASH"       # paid at ward counter
    ESEWA     = "ESEWA"
    KHALTI    = "KHALTI"
    CONNECT_IPS = "CONNECT_IPS"


class TaxDisputeStatus(str, enum.Enum):
    PENDING  = "PENDING"
    REVIEWED = "REVIEWED"
    RESOLVED = "RESOLVED"