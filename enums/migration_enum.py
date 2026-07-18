# ─────────────────────────────────────────────────────────────
# Add these enums into your existing model/enums.py
# (They are new — nothing here duplicates or replaces anything
# you already have. GenderType and RelatioshipType are reused
# as-is from your birth registration module.)
# ─────────────────────────────────────────────────────────────
import enum


class MigrationRegistrationStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class MigrationReasonType(str, enum.Enum):
    EMPLOYMENT = "EMPLOYMENT"       # रोजगारी
    STUDY = "STUDY"                 # अध्ययन
    BUSINESS = "BUSINESS"           # व्यवसाय
    MARRIAGE = "MARRIAGE"           # विवाह
    SETTLEMENT = "SETTLEMENT"       # बसोबास
    OTHER = "OTHER"                 # अन्य


class MigrationAddressType(str, enum.Enum):
    PERMANENT = "PERMANENT"   # स्थायी ठेगाना
    CURRENT = "CURRENT"       # हालको ठेगाना (address at time of leaving)
    NEW = "NEW"               # बसाईसराई गर्ने स्थान (migration destination)


class GenderType(str, enum.Enum):
    MALE    = "MALE"
    FEMALE  = "FEMALE"
    OTHERS  = "OTHERS"

class RelatioshipType(str, enum.Enum):
    FATHER = "बुबा"
    MOTHER = "आमा"
    GRANDFATHER = "हजुरबुबा"
    GRANDMOTHER = "हजुरआमा"
    GUARDIAN = "अभिभावक"
    OTHER = "अन्य"
