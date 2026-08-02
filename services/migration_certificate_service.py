import os
import uuid
import base64
from datetime import datetime, timezone

from model.migration_registration_model import MigrationCertificateModel
from schema.user_schema import RoleSchema

from services.certificate_service import (
    LOGO_PATH,
    to_nepali_digits,
    compute_data_hash,
    generate_qr,
    render_certificate_pdf,
    _find_chairperson,
    _role_value,
    _file_to_data_uri,
)

# Nepali labels for the OccupationType enum — keys must match
# enums/migration_enum.py OccupationType values exactly, same map used
# on the frontend preview.
OCCUPATION_NEPALI_MAP = {
    "FARMER": "कृषक",
    "SERVICE": "सेवा",
    "BUSINESS": "व्यवसाय",
    "STUDENT": "विद्यार्थी",
    "LABOUR": "मजदूर",
    "HOUSEWIFE": "गृहिणी",
    "UNEMPLOYED": "बेरोजगार",
    "OTHER": "अन्य",
}


def generate_migration_certificate_no(ward_no: int, year: int, sequence: int) -> str:
    return f"MC-{ward_no}-{year}-{sequence:05d}"


def _find_migration_signing_officer(ward):
    """
    Migration certificates are signed by the Ward Chairperson — checked
    first — falling back to the Ward Secretary only if no chairperson is
    on record for the ward.
    """
    chairperson = _find_chairperson(ward)
    if chairperson:
        return chairperson, "वडा अध्यक्ष", "Ward Chairperson"

    secretary = next(
        (u for u in ward.user if _role_value(u) == RoleSchema.WardSecretary.value),
        None,
    )
    if secretary:
        return secretary, "वडा सचिव", "Ward Secretary"

    return None, "वडा अध्यक्ष / वडा सचिव", "Ward Chairperson / Ward Secretary"


def _address_ctx(address_row):
    if not address_row:
        return {
            "province": "", "district": "", "municipality": "",
            "ward_number": "", "tole": "",
        }
    # Prefer the Nepali values captured at selection time
    # (province_np/district_np/municipality_np/ward_name_np); fall back to
    # the plain English fields only if an address predates those columns.
    return {
        "province": address_row.province_np or address_row.province,
        "district": address_row.district_np or address_row.district,
        "municipality": address_row.municipality_np or address_row.municipality,
        "ward_number": to_nepali_digits(address_row.ward_number),
        "tole": address_row.ward_name_np or address_row.tole,
    }


def issue_certificate_for_migration_registration(registration, db, issued_by_user_id):
    """
    Same shape as issue_certificate_for_death_registration, adapted for
    migration registrations: builds the certificate record, QR, hash, and
    PDF for a VERIFIED migration registration, and flips its status to
    CERTIFICATE_ISSUED.
    """

    if registration.certificate:
        raise ValueError("Certificate already issued for this registration")

    ward = registration.ward
    applicant = registration.applicant
    migration_detail = registration.migration_detail
    family_members = registration.family_members or []

    permanent_row = next(
        (a for a in registration.addresses if a.address_type.value == "PERMANENT"), None
    )
    new_row = next(
        (a for a in registration.addresses if a.address_type.value == "NEW"), None
    )

    signer, designation_np, designation_en = _find_migration_signing_officer(ward)

    year = registration.created_at.year
    sequence = (
        db.query(MigrationCertificateModel)
        .filter(MigrationCertificateModel.certificate_no.like(f"MC-{ward.ward_no}-{year}-%"))
        .count()
        + 1
    )
    certificate_no = generate_migration_certificate_no(ward.ward_no, year, sequence)

    hash_payload = {
        "migration_id": str(registration.migration_id),
        "certificate_no": certificate_no,
        "applicant_full_name": applicant.applicant_full_name_np,
        "migration_date_bs": migration_detail.migration_date_bs if migration_detail else None,
        "applicant_citizenship_no": applicant.applicant_citizenship_no,
    }
    data_hash = compute_data_hash(hash_payload)

    cert_id = uuid.uuid4()
    qr_path = generate_qr(cert_id)

    qr_abs_path = os.path.join("static", qr_path)
    with open(qr_abs_path, "rb") as f:
        qr_data_uri = "data:image/png;base64," + base64.b64encode(f.read()).decode()

    with open(LOGO_PATH, "rb") as f:
        logo_data_uri = "data:image/png;base64," + base64.b64encode(f.read()).decode()

    signer_signature_data_uri = _file_to_data_uri(
        getattr(signer, "signature_path", None)
    ) if signer else None
    stamp_data_uri = _file_to_data_uri(ward.chairperson_stamp_path)

    family_ctx = []
    for i, m in enumerate(family_members, start=1):
        family_ctx.append({
            "sn": to_nepali_digits(i),
            "name": m.member_name_np or m.member_name_en or "",
            "relationship": m.member_relationship.value if m.member_relationship else "",
            "gender": {"MALE": "पु.", "FEMALE": "म.", "OTHER": "अ."}.get(
                m.member_gender.value if m.member_gender else "", ""
            ),
            "dob_bs": to_nepali_digits(m.member_dob_bs) if m.member_dob_bs else "",
            "dob_ad": to_nepali_digits(m.member_dob_ad.strftime("%Y-%m-%d")) if m.member_dob_ad else "",
            "citizenship_no": to_nepali_digits(m.member_citizenship_no) if m.member_citizenship_no else "",
            "remarks": m.member_remarks or "",
        })

    # Pad the table to at least 5 rows so the printed form has blank lines
    # for handwritten additions, matching the reference form's layout.
    blank_family_rows = range(max(0, 5 - len(family_ctx)))

    occupation_value = applicant.applicant_occupation.value if hasattr(
        applicant.applicant_occupation, "value"
    ) else applicant.applicant_occupation

    template_context = {
        "certificate_no": to_nepali_digits(certificate_no),
        "registration_date": to_nepali_digits(registration.created_at.strftime("%Y-%m-%d")),
        "issue_date": to_nepali_digits(datetime.now(timezone.utc).strftime("%Y-%m-%d")),
        "ward": ward,
        "ward_no_np": to_nepali_digits(ward.ward_no),
        "applicant": {
            "full_name_np": applicant.applicant_full_name_np,
            "gender": applicant.applicant_gender.value if applicant.applicant_gender else None,
            "dob_bs": to_nepali_digits(applicant.applicant_dob_bs) if applicant.applicant_dob_bs else "",
            "dob_ad": to_nepali_digits(applicant.applicant_dob_ad.strftime("%Y-%m-%d")) if applicant.applicant_dob_ad else "",
            "citizenship_no": to_nepali_digits(applicant.applicant_citizenship_no),
            "nationality": applicant.applicant_nationality,
            "occupation": OCCUPATION_NEPALI_MAP.get(occupation_value, occupation_value or ""),
            "contact_no": to_nepali_digits(applicant.applicant_contact_no) if applicant.applicant_contact_no else "",
        },
        "permanent_address": _address_ctx(permanent_row),
        "new_address": _address_ctx(new_row),
        "migration_detail": {
            "migration_date_bs": to_nepali_digits(migration_detail.migration_date_bs) if migration_detail and migration_detail.migration_date_bs else "",
            "migration_date_ad": to_nepali_digits(migration_detail.migration_date_ad.strftime("%Y-%m-%d")) if migration_detail and migration_detail.migration_date_ad else "",
            "migration_reason": migration_detail.migration_reason.value if migration_detail and migration_detail.migration_reason else None,
            "migration_reason_other": migration_detail.migration_reason_other if migration_detail else "",
        },
        "family_members": family_ctx,
        "blank_family_rows": blank_family_rows,
        "recommender_name": None,  # no separate "recommending officer" role modeled yet — left blank on the form
        "recommender_designation": None,
        "logo_data_uri": logo_data_uri,
        "qr_data_uri": qr_data_uri,
        "signer_signature_data_uri": signer_signature_data_uri,
        "stamp_data_uri": stamp_data_uri,
        "signer_name": (signer.user_nepali_name or signer.user_name) if signer else None,
        "signer_designation_np": designation_np,
        "signer_designation_en": designation_en,
    }

    pdf_path = render_certificate_pdf(cert_id, template_context, template_name="migration_certificate.html")

    certificate = MigrationCertificateModel(
        cert_id=cert_id,
        migration_id=registration.migration_id,
        certificate_no=certificate_no,
        data_hash=data_hash,
        qr_path=qr_path,
        pdf_path=pdf_path,
        issued_by=issued_by_user_id,
    )
    db.add(certificate)
    registration.register_status = registration.register_status.__class__.CERTIFICATE_ISSUED
    db.commit()
    db.refresh(certificate)
    return certificate