import enum

class BirthRegistrationStatus(str, enum.Enum):
    DRAFT               = "DRAFT"
    SUBMITTED           = "SUBMITTED"
    DOCUMENT_REQUESTED  = "DOCUMENT_REQUESTED"
    APPROVED            = "APPROVED"
    CERTIFICATE_ISSUED  = "CERTIFICATE_ISSUED"
    REJECTED            = "REJECTED"
    VERIFIED=" VERIFIED"

class GenderType(str, enum.Enum):
    MALE    = "MALE"
    FEMALE  = "FEMALE"
    OTHERS  = "OTHERS"

class BirthPlaceType(str,enum.Enum):
    HOSPITAL="HOSPITAL"
    HOME="HOME"
    OUTER="OUTER"

class BirthKindType(str, enum.Enum):
    SINGLE          = "SINGLE"
    TWIN            = "SINGLE"
    TRIPLET_OR_MORE = "TRIPLET OR MORE"

class ParentType(str, enum.Enum):
    FATHER = "FATHER"
    MOTHER = "MOTHER"

class UserRoleType(str, enum.Enum):
    CITIZEN      = "CITIZEN"
    WARD_OFFICER = "WARD_OFFICER"
    REGISTRAR    = "REGISTRAR"
    ADMIN        = "ADMIN"

class DocumentType(str, enum.Enum):
    CITIZENSHIP_FATHER = "CITIZENSHIP_FATHER"
    CITIZENSHIP_MOTHER = "CITIZENSHIP_MOTHER"
    MARRIAGE_CERT      = "MARRIAGE_CERT"
    RESIDENCE_PROOF    = "RESIDENCE_PROOF"
    IN_MIGRATION_CERT  = "IN_MIGRATION_CERT"

class RelatioshipType(str,enum.Enum):
    FATHER="FATHER"
    MOTHER="MOTHER"
    GRANDFATHER="GRANDFATHER"
    GRANDMOTHER="GRANDMOTHER"
    GUARDIAN="GUARDIAN"
    OTHER="OTHER"