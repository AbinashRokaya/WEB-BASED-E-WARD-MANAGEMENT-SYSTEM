# enums/recommendation_enum.py
import enum

class RecommendationLetterType(str, enum.Enum):
    RESIDENCE_PROOF = "RESIDENCE_PROOF"           # बसोबास प्रमाणित
    UNMARRIED_STATUS = "UNMARRIED_STATUS"         # अविवाहित प्रमाणित
    CHARACTER_CERTIFICATE = "CHARACTER_CERTIFICATE"  # चालचलन प्रमाणित
    INCOME_STATEMENT = "INCOME_STATEMENT"         # आर्थिक अवस्था प्रमाणित
    RELATIONSHIP_PROOF = "RELATIONSHIP_PROOF"     # नाता प्रमाणित
    LAND_OWNERSHIP_PROOF = "LAND_OWNERSHIP_PROOF" # जग्गा स्वामित्व प्रमाणित
    OTHER = "OTHER"
# enums/recommendation_enum.py
class RecommendationStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"
    VERIFIED = "VERIFIED"
    CERTIFICATE_ISSUED = "CERTIFICATE_ISSUED"   # ← added
    REJECTED = "REJECTED"