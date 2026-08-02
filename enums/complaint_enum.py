import enum


class ComplaintCategory(str, enum.Enum):
    INFRASTRUCTURE    = "INFRASTRUCTURE"
    SERVICE_DELAY     = "SERVICE_DELAY"
    STAFF_MISCONDUCT  = "STAFF_MISCONDUCT"
    CORRUPTION        = "CORRUPTION"
    WATER_SUPPLY      = "WATER_SUPPLY"
    SANITATION        = "SANITATION"
    OTHER             = "OTHER"


# Categories where the secretary is often the subject of the complaint
# (or lacks authority to close it alone) — these MUST go to the chairperson.
# Everything else, the secretary can resolve directly.
ESCALATION_CATEGORIES = {
    ComplaintCategory.STAFF_MISCONDUCT,
    ComplaintCategory.CORRUPTION,
}


def requires_escalation(category: ComplaintCategory) -> bool:
    return category in ESCALATION_CATEGORIES


class ComplaintPriority(str, enum.Enum):
    LOW    = "LOW"
    MEDIUM = "MEDIUM"
    HIGH   = "HIGH"
    URGENT = "URGENT"


# DRAFT -> SUBMITTED -> APPROVED (officer) ->
#   either RESOLVED directly (secretary, non-escalation categories)
#   or VERIFIED (secretary forwards escalation categories) -> RESOLVED (chairperson)
# REJECTED is reachable from SUBMITTED, APPROVED, or VERIFIED.
class ComplaintStatus(str, enum.Enum):
    DRAFT     = "DRAFT"
    SUBMITTED = "SUBMITTED"
    APPROVED  = "APPROVED"
    VERIFIED  = "VERIFIED"
    RESOLVED  = "RESOLVED"
    REJECTED  = "REJECTED"


class AuthorRole(str, enum.Enum):
    CITIZEN     = "CITIZEN"
    OFFICER     = "OFFICER"
    SECRETARY   = "SECRETARY"
    CHAIRPERSON = "CHAIRPERSON"