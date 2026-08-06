# router/admin_analytics_router.py
"""
Admin-level ward analytics.

Your existing `analytics_router.py` scopes every query to
`current_user.user_ward_id`, so each officer role only ever sees their
own ward — that's correct for them, but admin needs two things that
router can't give:

  1. COUNTRY-WIDE numbers — the same shape of summary, aggregated
     across every ward, with a ward-breakdown table so admin can see
     which wards are lagging (not just a single national total).
  2. DRILL-DOWN — the ability to view any ONE ward's numbers by
     passing ward_id, not just their own.

This router reuses MODULE_CONFIG and _get_module_summary from your
existing analytics_router.py rather than redefining the five modules
(birth/death/migration/recommendation/complaint) a second time — if
you add a sixth module later, you only touch one place.

PERMISSION: gated on require_permission("delete_user"). Looking at
Permission_Role, every officer role (WardChairperson, WardSecretary,
DataValidationOfficer) and even Citizen carries "read_user", so that
permission alone can't distinguish admin from anyone else — but
"delete_user" is granted to SuperAdmin only. That makes it a correct
gate today, but it's a slightly awkward one to read at a glance. If
you'd rather have a self-documenting check, add a dedicated permission
(e.g. "view_admin_analytics") to SuperAdmin's set in Permission_Role
and swap the string below — behavior is identical either way.

WardModel: _ward_label() assumes ward_id plus either ward_name or
ward_no. Adjust the import path and the field lookups to match your
actual model if they differ.

WARD_ID TYPE: ward_id columns are UUID, not int. Every query param
below is Optional[str] and gets parsed through _parse_ward_id() into
a real uuid.UUID before it touches a query, and every UUID that ends
up in a response dict is explicitly str()'d — json.dumps() cannot
serialize a raw UUID object and will 500 (which surfaces client-side
as a misleading CORS error, since a 500 from an unhandled exception
skips the CORS middleware's headers on some setups).
"""
import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import extract, func

from auth.current_user import require_permission
from database.db import get_db

# Reuse the module config + single-ward aggregation logic already
# written and tested in the officer-facing router — don't duplicate it.
from route.analytics_router import MODULE_CONFIG, _get_module_summary

from model.birth_registration_model import BirthRegistrationModel
from model.death_registration_model import (
    DeathRegistrationModel, DeceasedModel, DeathDetailModel,
)
from model.migration_registration_model import (
    MigrationRegistrationModel, MigrationDetailModel,
)
from model.complaint_model import ComplaintModel
from model.ward_model import WardModel  # adjust import path if different

router = APIRouter(
    prefix="/v1/analytics/admin",
    tags=["analytics-admin"],
)


def _ward_label(ward: WardModel) -> str:
    return ward.ward_name or f"Ward {ward.ward_no}"


def _ward_lookup(db) -> dict:
    """ward_id (UUID) -> display name, for stamping names onto
    ward_breakdown and births_by_ward rows below. Keyed by the raw
    UUID object — callers must look up with the raw UUID *before*
    stringifying it for the response. No dedicated /wards endpoint
    here — the frontend already has the full ward list (with
    ward_district / ward_municipality for its own cascading selector)
    from the existing ward-management fetch, so this router doesn't
    need to serve it a second time."""
    return {w.ward_id: _ward_label(w) for w in db.query(WardModel).all()}


def _parse_ward_id(ward_id: Optional[str]) -> Optional[uuid.UUID]:
    """Query params arrive as strings; ward_id columns are UUID.
    Parse explicitly so a bad value fails with a clear 400 instead of
    a confusing type error (or an accidental int-vs-UUID mismatch)
    deep inside a query filter."""
    if ward_id is None:
        return None
    try:
        return uuid.UUID(ward_id)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid ward_id '{ward_id}'")


# ══════════════════════════════════════════════════════════════
# COUNTRY-WIDE MODULE SUMMARY — same fields as the officer-facing
# /summary endpoint (status_summary, monthly_trend, pending_aging,
# recent_rejection_reasons) but aggregated over every ward, plus a
# ward_breakdown list that's the actual point of an admin view: not
# just "what's the national total" but "which wards are behind".
# ══════════════════════════════════════════════════════════════

def _get_country_module_summary(db, module_key: str, year: int) -> dict:
    cfg = MODULE_CONFIG[module_key]
    Model, status_col, ward_col, id_col = cfg["model"], cfg["status_col"], cfg["ward_col"], cfg["id_col"]

    # 1. status breakdown — all wards, all-time
    status_rows = db.query(status_col, func.count(id_col)).group_by(status_col).all()
    status_summary = {status.value: count for status, count in status_rows}

    # 2. monthly submission count, selected year, all wards
    monthly_rows = (
        db.query(extract("month", Model.created_at).label("m"), func.count(id_col))
        .filter(extract("year", Model.created_at) == year)
        .group_by("m")
        .all()
    )
    monthly_map = {int(m): c for m, c in monthly_rows}
    monthly_trend = [{"month": i, "submitted": monthly_map.get(i, 0)} for i in range(1, 13)]

    total = sum(status_summary.values())
    issued = status_summary.get(cfg["issued_status"], 0)
    rejected = status_summary.get("REJECTED", 0)
    completion_rate = round((issued / total) * 100, 1) if total else 0

    # 3. most recent rejection reasons, across all wards
    RejectModel_, reject_fk_col = cfg["reject_model"], cfg["reject_fk_col"]
    reject_rows = (
        db.query(RejectModel_.reject_text)
        .join(Model, reject_fk_col == id_col)
        .filter(RejectModel_.reject_text.isnot(None))
        .order_by(RejectModel_.reject_id.desc())
        .limit(15)
        .all()
    )
    recent_rejection_reasons = [r[0] for r in reject_rows if r[0]]

    # 4. pending aging, across all wards
    pending_rows = db.query(Model.created_at).filter(~status_col.in_(list(cfg["terminal_statuses"]))).all()
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

    # 5. per-ward breakdown — group by (ward, status) in one query rather
    # than looping _get_module_summary() per ward, which would be N+1.
    ward_status_rows = (
        db.query(ward_col, status_col, func.count(id_col))
        .group_by(ward_col, status_col)
        .all()
    )
    per_ward: dict = {}
    for w_id, status, count in ward_status_rows:
        entry = per_ward.setdefault(w_id, {"ward_id": w_id, "total": 0, "issued": 0, "rejected": 0})
        entry["total"] += count
        if status.value == cfg["issued_status"]:
            entry["issued"] += count
        elif status.value == "REJECTED":
            entry["rejected"] += count

    ward_names = _ward_lookup(db)
    ward_breakdown = []
    for w_id, entry in per_ward.items():
        # Look up the display name with the raw UUID (w_id) BEFORE
        # overwriting entry["ward_id"] with its string form below —
        # ward_names is keyed by raw UUID objects.
        entry["ward_name"] = ward_names.get(w_id, f"Ward {w_id}")
        entry["completion_rate"] = round((entry["issued"] / entry["total"]) * 100, 1) if entry["total"] else 0
        entry["ward_id"] = str(entry["ward_id"])  # UUID -> str, JSON-safe
        ward_breakdown.append(entry)
    ward_breakdown.sort(key=lambda w: w["total"], reverse=True)

    return {
        "module": module_key,
        "year": year,
        "scope": "country",
        "status_summary": status_summary,
        "monthly_trend": monthly_trend,
        "total": total,
        "issued": issued,
        "rejected": rejected,
        "completion_rate": completion_rate,
        "recent_rejection_reasons": recent_rejection_reasons,
        "pending_aging": aging_buckets,
        "ward_breakdown": ward_breakdown,
    }


@router.get("/{module}/summary")
def admin_module_summary(
    module: str,
    year: Optional[int] = None,
    ward_id: Optional[str] = None,
    db=Depends(get_db),
    current_user=Depends(require_permission("delete_user")),
):
    """
    No ward_id -> country-wide summary + ward_breakdown for comparison.
    ward_id given -> drill into that one ward (any ward, not just the
    caller's own — that's what makes this an admin endpoint).
    """
    if module not in MODULE_CONFIG:
        raise HTTPException(status_code=404, detail=f"Unknown analytics module '{module}'")

    year = year or datetime.utcnow().year
    parsed_ward_id = _parse_ward_id(ward_id)

    if parsed_ward_id is not None:
        data = _get_module_summary(db, parsed_ward_id, module, year)
        data["scope"] = "ward"
        data["ward_id"] = str(parsed_ward_id)
    else:
        data = _get_country_module_summary(db, module, year)

    return JSONResponse(
        status_code=200,
        content={"success": True, "status_code": 200, "message": "Analytics fetched successfully", "data": data},
    )


# ══════════════════════════════════════════════════════════════
# WARD LEADERBOARD — dedicated endpoint for a comparison table/chart,
# so the frontend doesn't have to pull the full country summary just
# to render a ward-vs-ward ranking.
# ══════════════════════════════════════════════════════════════

@router.get("/wards/leaderboard")
def wards_leaderboard(
    module: str,
    year: Optional[int] = None,
    db=Depends(get_db),
    current_user=Depends(require_permission("delete_user")),
):
    if module not in MODULE_CONFIG:
        raise HTTPException(status_code=404, detail=f"Unknown analytics module '{module}'")
    year = year or datetime.utcnow().year
    data = _get_country_module_summary(db, module, year)
    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "status_code": 200,
            "message": "Ward leaderboard fetched successfully",
            "data": {"module": module, "year": year, "wards": data["ward_breakdown"]},
        },
    )


# ══════════════════════════════════════════════════════════════
# VITAL SNAPSHOT — country-wide by default, or a single ward via
# ward_id. Country-wide also returns births_by_ward, since that's the
# volume comparison admin actually wants without a population field.
# ══════════════════════════════════════════════════════════════

@router.get("/vital-snapshot")
def admin_vital_snapshot(
    year: Optional[int] = None,
    ward_id: Optional[str] = None,
    db=Depends(get_db),
    current_user=Depends(require_permission("delete_user")),
):
    year = year or datetime.utcnow().year
    parsed_ward_id = _parse_ward_id(ward_id)

    births_q = db.query(func.count(BirthRegistrationModel.registration_id)).filter(
        extract("year", BirthRegistrationModel.created_at) == year
    )
    deaths_q = db.query(func.count(DeathRegistrationModel.registration_id)).filter(
        extract("year", DeathRegistrationModel.created_at) == year
    )
    migrations_q = db.query(func.count(MigrationRegistrationModel.migration_id)).filter(
        extract("year", MigrationRegistrationModel.created_at) == year
    )

    if parsed_ward_id is not None:
        births_q = births_q.filter(BirthRegistrationModel.register_ward_id == parsed_ward_id)
        deaths_q = deaths_q.filter(DeathRegistrationModel.register_ward_id == parsed_ward_id)
        migrations_q = migrations_q.filter(MigrationRegistrationModel.register_ward_id == parsed_ward_id)

    births, deaths, migrations = births_q.scalar(), deaths_q.scalar(), migrations_q.scalar()

    data = {
        "year": year,
        "scope": "ward" if parsed_ward_id is not None else "country",
        "ward_id": str(parsed_ward_id) if parsed_ward_id is not None else None,
        "births": births,
        "deaths": deaths,
        "migrations": migrations,
        "natural_change": births - deaths,
    }

    if parsed_ward_id is None:
        birth_by_ward = (
            db.query(BirthRegistrationModel.register_ward_id, func.count(BirthRegistrationModel.registration_id))
            .filter(extract("year", BirthRegistrationModel.created_at) == year)
            .group_by(BirthRegistrationModel.register_ward_id)
            .all()
        )
        ward_names = _ward_lookup(db)
        data["births_by_ward"] = sorted(
            (
                {"ward_id": str(w_id), "ward_name": ward_names.get(w_id, f"Ward {w_id}"), "births": count}
                for w_id, count in birth_by_ward
            ),
            key=lambda w: w["births"],
            reverse=True,
        )

    return JSONResponse(
        status_code=200,
        content={"success": True, "status_code": 200, "message": "Vital snapshot fetched successfully", "data": data},
    )


# ══════════════════════════════════════════════════════════════
# DEATH / MIGRATION / COMPLAINT — same shape as the officer-facing
# endpoints, with an optional ward_id filter. No ward_id = national.
# ══════════════════════════════════════════════════════════════

@router.get("/death/causes")
def admin_death_cause_breakdown(
    ward_id: Optional[str] = None,
    db=Depends(get_db),
    current_user=Depends(require_permission("delete_user")),
):
    parsed_ward_id = _parse_ward_id(ward_id)

    q_cause = db.query(DeathDetailModel.death_type, func.count(DeathDetailModel.death_detail_id)).join(
        DeathRegistrationModel, DeathDetailModel.registration_id == DeathRegistrationModel.registration_id
    )
    q_age = (
        db.query(DeceasedModel.deceased_age_years)
        .join(DeathRegistrationModel, DeceasedModel.registration_id == DeathRegistrationModel.registration_id)
        .filter(DeceasedModel.deceased_age_years.isnot(None))
    )

    if parsed_ward_id is not None:
        q_cause = q_cause.filter(DeathRegistrationModel.register_ward_id == parsed_ward_id)
        q_age = q_age.filter(DeathRegistrationModel.register_ward_id == parsed_ward_id)

    cause_breakdown = {c.value: n for c, n in q_cause.group_by(DeathDetailModel.death_type).all()}

    age_buckets = {"0-17": 0, "18-40": 0, "41-60": 0, "61-80": 0, "80+": 0}
    for (age,) in q_age.all():
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


@router.get("/migration/reasons")
def admin_migration_reason_breakdown(
    ward_id: Optional[str] = None,
    db=Depends(get_db),
    current_user=Depends(require_permission("delete_user")),
):
    parsed_ward_id = _parse_ward_id(ward_id)

    q = db.query(MigrationDetailModel.migration_reason, func.count(MigrationDetailModel.migration_detail_id)).join(
        MigrationRegistrationModel, MigrationDetailModel.migration_id == MigrationRegistrationModel.migration_id
    )
    if parsed_ward_id is not None:
        q = q.filter(MigrationRegistrationModel.register_ward_id == parsed_ward_id)

    reason_breakdown = {reason.value: count for reason, count in q.group_by(MigrationDetailModel.migration_reason).all()}

    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "status_code": 200,
            "message": "Migration reason breakdown fetched successfully",
            "data": {"reason_breakdown": reason_breakdown},
        },
    )


@router.get("/complaint/breakdown")
def admin_complaint_breakdown(
    ward_id: Optional[str] = None,
    db=Depends(get_db),
    current_user=Depends(require_permission("delete_user")),
):
    parsed_ward_id = _parse_ward_id(ward_id)

    category_q = db.query(ComplaintModel.complaint_category, func.count(ComplaintModel.complaint_id))
    priority_q = db.query(ComplaintModel.complaint_priority, func.count(ComplaintModel.complaint_id))
    resolved_q = db.query(ComplaintModel.created_at, ComplaintModel.resolved_at, ComplaintModel.sla_deadline).filter(
        ComplaintModel.resolved_at.isnot(None)
    )

    if parsed_ward_id is not None:
        category_q = category_q.filter(ComplaintModel.complaint_ward_id == parsed_ward_id)
        priority_q = priority_q.filter(ComplaintModel.complaint_ward_id == parsed_ward_id)
        resolved_q = resolved_q.filter(ComplaintModel.complaint_ward_id == parsed_ward_id)

    category_rows = category_q.group_by(ComplaintModel.complaint_category).all()
    priority_rows = priority_q.group_by(ComplaintModel.complaint_priority).all()
    resolved_rows = resolved_q.all()

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