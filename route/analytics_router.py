# router/analytics_router.py
"""
Ward analytics — one router, shared across all three review roles
(data validation officer, ward secretary, ward chairperson). No role
check beyond `read_user` is needed: every query is scoped to
`current_user.user_ward_id`, exactly like the other officer-facing
routers in this project, so each role only ever sees their own ward.
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import extract, func

from auth.current_user import require_permission
from database.db import get_db

# ── Birth ──────────────────────────────────────────────
from model.birth_registration_model import BirthRegistrationModel, RejectModel
from model.enums import BirthRegistrationStatus

# ── Death ──────────────────────────────────────────────
from model.death_registration_model import (
    DeathRegistrationModel, DeathRejectModel, DeceasedModel, DeathDetailModel,
)
from enums.death_enum import DeathRegistrationStatus

# ── Migration ────────────────────────────────────────────
from model.migration_registration_model import (
    MigrationRegistrationModel, MigrationRejectModel, MigrationDetailModel,
)
from enums.migration_enum import MigrationRegistrationStatus

# ── Recommendation ───────────────────────────────────────
from model.recommendation_model import RecommendationLetterModel, RecommendationRejectModel
from enums.recommendation_enum import RecommendationStatus

# ── Complaint ────────────────────────────────────────────
from model.complaint_model import ComplaintModel, ComplaintRejectModel
from enums.complaint_enum import ComplaintStatus

router = APIRouter(
    prefix="/v1/analytics",
    tags=["analytics"],
)

# ══════════════════════════════════════════════════════════════
# MODULE CONFIG — the five registration-style modules share the same
# shape (a status column, a ward column, a primary-key column,
# created_at, and a reject table with a reject_text column), just
# under different names. One config dict avoids writing near-identical
# service code five times.
# ══════════════════════════════════════════════════════════════

MODULE_CONFIG = {
    "birth": dict(
        model=BirthRegistrationModel,
        status_col=BirthRegistrationModel.register_status,
        ward_col=BirthRegistrationModel.register_ward_id,
        id_col=BirthRegistrationModel.registration_id,
        reject_model=RejectModel,
        reject_fk_col=RejectModel.registration_id,
        issued_status="CERTIFICATE_ISSUED",
        terminal_statuses={"CERTIFICATE_ISSUED", "REJECTED"},
    ),
    "death": dict(
        model=DeathRegistrationModel,
        status_col=DeathRegistrationModel.register_status,
        ward_col=DeathRegistrationModel.register_ward_id,
        id_col=DeathRegistrationModel.registration_id,
        reject_model=DeathRejectModel,
        reject_fk_col=DeathRejectModel.registration_id,
        issued_status="CERTIFICATE_ISSUED",
        terminal_statuses={"CERTIFICATE_ISSUED", "REJECTED"},
    ),
    "migration": dict(
        model=MigrationRegistrationModel,
        status_col=MigrationRegistrationModel.register_status,
        ward_col=MigrationRegistrationModel.register_ward_id,
        id_col=MigrationRegistrationModel.migration_id,
        reject_model=MigrationRejectModel,
        reject_fk_col=MigrationRejectModel.migration_id,
        issued_status="CERTIFICATE_ISSUED",
        terminal_statuses={"CERTIFICATE_ISSUED", "REJECTED"},
    ),
    "recommendation": dict(
        model=RecommendationLetterModel,
        status_col=RecommendationLetterModel.register_status,
        ward_col=RecommendationLetterModel.register_ward_id,
        id_col=RecommendationLetterModel.letter_id,
        reject_model=RecommendationRejectModel,
        reject_fk_col=RecommendationRejectModel.letter_id,
        issued_status="CERTIFICATE_ISSUED",
        terminal_statuses={"CERTIFICATE_ISSUED", "REJECTED"},
    ),
    "complaint": dict(
        model=ComplaintModel,
        status_col=ComplaintModel.complaint_status,
        ward_col=ComplaintModel.complaint_ward_id,
        id_col=ComplaintModel.complaint_id,
        reject_model=ComplaintRejectModel,
        reject_fk_col=ComplaintRejectModel.complaint_id,
        issued_status="RESOLVED",  # complaints resolve, they don't issue a certificate
        terminal_statuses={"RESOLVED", "REJECTED"},
    ),
}


def _get_module_summary(db, ward_id, module_key: str, year: int) -> dict:
    cfg = MODULE_CONFIG[module_key]
    Model, status_col, ward_col, id_col = cfg["model"], cfg["status_col"], cfg["ward_col"], cfg["id_col"]

    # 1. status breakdown — all-time, this ward
    status_rows = (
        db.query(status_col, func.count(id_col))
        .filter(ward_col == ward_id)
        .group_by(status_col)
        .all()
    )
    status_summary = {status.value: count for status, count in status_rows}

    # 2. monthly submission count for the selected year
    monthly_rows = (
        db.query(extract("month", Model.created_at).label("m"), func.count(id_col))
        .filter(ward_col == ward_id, extract("year", Model.created_at) == year)
        .group_by("m")
        .all()
    )
    monthly_map = {int(m): c for m, c in monthly_rows}
    monthly_trend = [{"month": i, "submitted": monthly_map.get(i, 0)} for i in range(1, 13)]

    total = sum(status_summary.values())
    issued = status_summary.get(cfg["issued_status"], 0)
    rejected = status_summary.get("REJECTED", 0)
    completion_rate = round((issued / total) * 100, 1) if total else 0

    # 3. most recent rejection reasons — reject_text is free-form Text in
    # your schema, not a category, so this is a short list for staff to
    # read, not something to chart as categorical bars.
    RejectModel_, reject_fk_col = cfg["reject_model"], cfg["reject_fk_col"]
    reject_rows = (
        db.query(RejectModel_.reject_text)
        .join(Model, reject_fk_col == id_col)
        .filter(ward_col == ward_id, RejectModel_.reject_text.isnot(None))
        .order_by(RejectModel_.reject_id.desc())
        .limit(10)
        .all()
    )
    recent_rejection_reasons = [r[0] for r in reject_rows if r[0]]

    # 4. pending aging — how long currently-pending records have been
    # waiting, bucketed. This is what stands in for a "backlog trend"
    # without a status-history table: you can't reconstruct what the
    # backlog looked like last month, but you can see how stale today's
    # backlog already is.
    pending_rows = (
        db.query(Model.created_at)
        .filter(ward_col == ward_id, ~status_col.in_(list(cfg["terminal_statuses"])))
        .all()
    )
    now = datetime.utcnow()
    aging_buckets = {"0-3 days": 0, "4-7 days": 0, "8-14 days": 0, "15-30 days": 0, "30+ days": 0}
    for (created_at,) in pending_rows:
        age_days = (now - created_at).days
        if age_days <= 3:
            aging_buckets["0-3 days"] += 1
        elif age_days <= 7:
            aging_buckets["4-7 days"] += 1
        elif age_days <= 14:
            aging_buckets["8-14 days"] += 1
        elif age_days <= 30:
            aging_buckets["15-30 days"] += 1
        else:
            aging_buckets["30+ days"] += 1

    return {
        "module": module_key,
        "year": year,
        "status_summary": status_summary,
        "monthly_trend": monthly_trend,
        "total": total,
        "issued": issued,
        "rejected": rejected,
        "completion_rate": completion_rate,
        "recent_rejection_reasons": recent_rejection_reasons,
        "pending_aging": aging_buckets,
    }


@router.get("/{module}/summary")
def module_summary(
    module: str,
    year: Optional[int] = None,
    db=Depends(get_db),
    current_user=Depends(require_permission("read_user")),
):
    if module not in MODULE_CONFIG:
        raise HTTPException(status_code=404, detail=f"Unknown analytics module '{module}'")
    if not current_user.user_ward_id:
        raise HTTPException(status_code=422, detail="Your account has no registered ward on file.")

    year = year or datetime.utcnow().year
    data = _get_module_summary(db, current_user.user_ward_id, module, year)

    return JSONResponse(
        status_code=200,
        content={"success": True, "status_code": 200, "message": "Analytics fetched successfully", "data": data},
    )


# ══════════════════════════════════════════════════════════════
# WARD-WIDE VITAL SNAPSHOT — births + deaths for the year, independent
# of which module tab is selected in the frontend. Migration is counted
# but NOT split into in/out, since there's no direction field on
# MigrationRegistrationModel yet (see note in the response below).
# ══════════════════════════════════════════════════════════════

@router.get("/vital-snapshot")
def vital_snapshot(
    year: Optional[int] = None,
    db=Depends(get_db),
    current_user=Depends(require_permission("read_user")),
):
    if not current_user.user_ward_id:
        raise HTTPException(status_code=422, detail="Your account has no registered ward on file.")

    ward_id = current_user.user_ward_id
    year = year or datetime.utcnow().year

    births = db.query(func.count(BirthRegistrationModel.registration_id)).filter(
        BirthRegistrationModel.register_ward_id == ward_id,
        extract("year", BirthRegistrationModel.created_at) == year,
    ).scalar()

    deaths = db.query(func.count(DeathRegistrationModel.registration_id)).filter(
        DeathRegistrationModel.register_ward_id == ward_id,
        extract("year", DeathRegistrationModel.created_at) == year,
    ).scalar()

    migrations = db.query(func.count(MigrationRegistrationModel.migration_id)).filter(
        MigrationRegistrationModel.register_ward_id == ward_id,
        extract("year", MigrationRegistrationModel.created_at) == year,
    ).scalar()

    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "status_code": 200,
            "message": "Vital snapshot fetched successfully",
            "data": {
                "year": year,
                "births": births,
                "deaths": deaths,
                "migrations": migrations,
                "natural_change": births - deaths,
                # population-based rates (per 1,000) need a `population`
                # field on WardModel — not present yet, so left to the
                # frontend to compute once/if that field is added.
            },
        },
    )


# ══════════════════════════════════════════════════════════════
# DEATH — cause-of-death + age-at-death breakdown. Real fields:
# DeathDetailModel.death_type, DeceasedModel.deceased_age_years.
# ══════════════════════════════════════════════════════════════

@router.get("/death/causes")
def death_cause_breakdown(
    db=Depends(get_db),
    current_user=Depends(require_permission("read_user")),
):
    ward_id = current_user.user_ward_id

    cause_rows = (
        db.query(DeathDetailModel.death_type, func.count(DeathDetailModel.death_detail_id))
        .join(DeathRegistrationModel, DeathDetailModel.registration_id == DeathRegistrationModel.registration_id)
        .filter(DeathRegistrationModel.register_ward_id == ward_id)
        .group_by(DeathDetailModel.death_type)
        .all()
    )
    cause_breakdown = {cause.value: count for cause, count in cause_rows}

    age_rows = (
        db.query(DeceasedModel.deceased_age_years)
        .join(DeathRegistrationModel, DeceasedModel.registration_id == DeathRegistrationModel.registration_id)
        .filter(DeathRegistrationModel.register_ward_id == ward_id, DeceasedModel.deceased_age_years.isnot(None))
        .all()
    )
    age_buckets = {"0-17": 0, "18-40": 0, "41-60": 0, "61-80": 0, "80+": 0}
    for (age,) in age_rows:
        if age <= 17:
            age_buckets["0-17"] += 1
        elif age <= 40:
            age_buckets["18-40"] += 1
        elif age <= 60:
            age_buckets["41-60"] += 1
        elif age <= 80:
            age_buckets["61-80"] += 1
        else:
            age_buckets["80+"] += 1

    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "status_code": 200,
            "message": "Death breakdown fetched successfully",
            "data": {"cause_breakdown": cause_breakdown, "age_distribution": age_buckets},
        },
    )


# ══════════════════════════════════════════════════════════════
# MIGRATION — reason breakdown. Real field:
# MigrationDetailModel.migration_reason.
# ══════════════════════════════════════════════════════════════

@router.get("/migration/reasons")
def migration_reason_breakdown(
    db=Depends(get_db),
    current_user=Depends(require_permission("read_user")),
):
    ward_id = current_user.user_ward_id

    rows = (
        db.query(MigrationDetailModel.migration_reason, func.count(MigrationDetailModel.migration_detail_id))
        .join(MigrationRegistrationModel, MigrationDetailModel.migration_id == MigrationRegistrationModel.migration_id)
        .filter(MigrationRegistrationModel.register_ward_id == ward_id)
        .group_by(MigrationDetailModel.migration_reason)
        .all()
    )
    reason_breakdown = {reason.value: count for reason, count in rows}

    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "status_code": 200,
            "message": "Migration reason breakdown fetched successfully",
            "data": {"reason_breakdown": reason_breakdown},
        },
    )


# ══════════════════════════════════════════════════════════════
# COMPLAINT — category + priority breakdown, plus SLA compliance and
# average resolution time, using the resolved_at / sla_deadline columns
# that already exist on ComplaintModel.
# ══════════════════════════════════════════════════════════════

@router.get("/complaint/breakdown")
def complaint_breakdown(
    db=Depends(get_db),
    current_user=Depends(require_permission("read_user")),
):
    ward_id = current_user.user_ward_id

    category_rows = (
        db.query(ComplaintModel.complaint_category, func.count(ComplaintModel.complaint_id))
        .filter(ComplaintModel.complaint_ward_id == ward_id)
        .group_by(ComplaintModel.complaint_category)
        .all()
    )
    priority_rows = (
        db.query(ComplaintModel.complaint_priority, func.count(ComplaintModel.complaint_id))
        .filter(ComplaintModel.complaint_ward_id == ward_id)
        .group_by(ComplaintModel.complaint_priority)
        .all()
    )

    resolved_rows = (
        db.query(ComplaintModel.created_at, ComplaintModel.resolved_at, ComplaintModel.sla_deadline)
        .filter(ComplaintModel.complaint_ward_id == ward_id, ComplaintModel.resolved_at.isnot(None))
        .all()
    )
    total_resolved = len(resolved_rows)
    within_sla = sum(1 for _, resolved_at, deadline in resolved_rows if deadline is not None and resolved_at <= deadline)
    avg_resolution_days = (
        round(sum((r - c).total_seconds() for c, r, _ in resolved_rows) / total_resolved / 86400, 1)
        if total_resolved else 0
    )
    sla_compliance_pct = round((within_sla / total_resolved) * 100, 1) if total_resolved else None

    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "status_code": 200,
            "message": "Complaint breakdown fetched successfully",
            "data": {
                "category_breakdown": {c.value: n for c, n in category_rows},
                "priority_breakdown": {p.value: n for p, n in priority_rows},
                "avg_resolution_days": avg_resolution_days,
                "sla_compliance_pct": sla_compliance_pct,
                "total_resolved": total_resolved,
            },
        },
    )