# ── Append these to your existing model/enums.py ──
# (GenderType and RelatioshipType are already defined there and are reused as-is)
import enum
class DeathRegistrationStatus(str, enum.Enum):
    DRAFT               = "DRAFT"
    SUBMITTED           = "SUBMITTED"
    DOCUMENT_REQUESTED  = "DOCUMENT_REQUESTED"
    APPROVED            = "APPROVED"
    CERTIFICATE_ISSUED  = "CERTIFICATE_ISSUED"
    REJECTED            = "REJECTED"
    VERIFIED            = "VERIFIED"


class MaritalStatusType(str, enum.Enum):
    UNMARRIED = "UNMARRIED"          # अविवाहित
    MARRIED   = "MARRIED"            # विवाहित
    WIDOWED   = "WIDOWED"            # विधुर/विधवा
    OTHER     = "OTHER"              # अन्य


class DeathTimePeriodType(str, enum.Enum):
    MORNING   = "MORNING"            # बिहान
    AFTERNOON = "AFTERNOON"          # दिउँसो
    EVENING   = "EVENING"            # साँझ
    NIGHT     = "NIGHT"              # राति


class DeathPlaceType(str, enum.Enum):
    HOME     = "HOME"                # घर
    HOSPITAL = "HOSPITAL"            # अस्पताल
    OTHER    = "OTHER"               # अन्य (खुले)


class DeathCauseType(str, enum.Enum):
    NATURAL  = "NATURAL"             # प्राकृतिक
    ACCIDENT = "ACCIDENT"            # दुर्घटना
    SUICIDE  = "SUICIDE"             # आत्महत्या
    HOMICIDE = "HOMICIDE"            # हत्या
    OTHER    = "OTHER"               # अन्य (खुले)


class DeathDocumentType(str, enum.Enum):
    DECEASED_CITIZENSHIP = "DECEASED_CITIZENSHIP"   # मृतकको नागरिकता प्रतिलिपि
    HOSPITAL_RECOMMENDATION = "HOSPITAL_RECOMMENDATION"  # अस्पताल/स्वास्थ्य संस्थाको सिफारिस
    OTHER = "OTHER"                                  # अन्य


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
