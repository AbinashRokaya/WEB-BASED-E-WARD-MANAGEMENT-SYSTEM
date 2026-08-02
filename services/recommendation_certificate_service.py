# services/recommendation_certificate_service.py
import os
import uuid
import base64
from datetime import datetime, timezone

from model.recommendation_model import RecommendationCertificateModel
from enums.recommendation_enum import RecommendationLetterType
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
    _ward_type_value,
    _WARD_TYPE_LABELS,
)

# ── Per letter-type subject line + certifying clause ──────────────────────
# subject_np / subject_en -> used as the letter's "विषय" line
# clause -> the specific fact being certified, dropped into the body paragraph
LETTER_TYPE_INFO = {
    RecommendationLetterType.RESIDENCE_PROOF: {
        "subject_np": "बसोबास प्रमाणित सम्बन्धमा",
        "subject_en": "Regarding Residence Verification",
        "clause": "हाल यस वडा क्षेत्रमा स्थायी बसोबास गरी बसेको",
    },
    RecommendationLetterType.UNMARRIED_STATUS: {
        "subject_np": "अविवाहित प्रमाणित सम्बन्धमा",
        "subject_en": "Regarding Unmarried Status Verification",
        "clause": "हालसम्म विवाह नगरी अविवाहित रहेको",
    },
    RecommendationLetterType.CHARACTER_CERTIFICATE: {
        "subject_np": "चालचलन प्रमाणित सम्बन्धमा",
        "subject_en": "Regarding Character Certificate",
        "clause": "यस वडा क्षेत्रमा असल चालचलन कायम राखी बसेको",
    },
    RecommendationLetterType.INCOME_STATEMENT: {
        "subject_np": "आर्थिक अवस्था प्रमाणित सम्बन्धमा",
        "subject_en": "Regarding Income Statement Verification",
        "clause": "यस वडा क्षेत्रमा बसोबास गर्दै सामान्य आर्थिक अवस्था भएको",
    },
    RecommendationLetterType.RELATIONSHIP_PROOF: {
        "subject_np": "नाता प्रमाणित सम्बन्धमा",
        "subject_en": "Regarding Relationship Verification",
        "clause": "निवेदनमा उल्लेखित व्यक्तिसँग नाता सम्बन्ध कायम रहेको",
    },
    RecommendationLetterType.LAND_OWNERSHIP_PROOF: {
        "subject_np": "जग्गा स्वामित्व प्रमाणित सम्बन्धमा",
        "subject_en": "Regarding Land Ownership Verification",
        "clause": "यस वडा क्षेत्र भित्र जग्गा स्वामित्व राखी बसेको",
    },
    RecommendationLetterType.OTHER: {
        "subject_np": "सिफारिस सम्बन्धमा",
        "subject_en": "Regarding Recommendation",
        "clause": None,  # filled from letter_type_other at runtime
    },
}


def generate_recommendation_certificate_no(ward_no: int, year: int, sequence: int) -> str:
    return f"RC-{ward_no}-{year}-{sequence:05d}"


def _build_applicant_address_line(province, district, municipality, ward_number, tole):
    parts = [
        p for p in [
            f"{district} जिल्ला" if district else None,
            municipality,
            f"वडा नं. {to_nepali_digits(ward_number)}" if ward_number else None,
            tole,
        ] if p
    ]
    return ", ".join(parts)


def issue_certificate_for_recommendation_letter(letter, db, issued_by_user_id):
    """
    Same shape as issue_certificate_for_registration (birth), adapted for
    recommendation letters. Unlike death certificates (secretary OR
    chairperson), recommendation letters are always signed by the Ward
    Chairperson — matching the reference सिफारिस letter format.

    Status flow mirrors birth exactly: the letter must be VERIFIED (by the
    ward secretary) before the chairperson can call this, and on success
    the letter moves to CERTIFICATE_ISSUED — not APPROVED — same terminal
    status name as BirthRegistrationModel uses.
    """

    if letter.certificate:
        raise ValueError("Certificate already issued for this letter")

    ward = letter.ward
    chairperson = _find_chairperson(ward)

    year = letter.created_at.year
    sequence = (
        db.query(RecommendationCertificateModel)
        .filter(RecommendationCertificateModel.certificate_no.like(f"RC-{ward.ward_no}-{year}-%"))
        .count()
        + 1
    )
    certificate_no = generate_recommendation_certificate_no(ward.ward_no, year, sequence)

    type_info = LETTER_TYPE_INFO[letter.letter_type]
    clause = type_info["clause"] or letter.letter_type_other or ""
    subject_np = (
        f"{letter.letter_type_other} सम्बन्धमा"
        if letter.letter_type == RecommendationLetterType.OTHER and letter.letter_type_other
        else type_info["subject_np"]
    )

    hash_payload = {
        "letter_id": str(letter.letter_id),
        "certificate_no": certificate_no,
        "applicant_full_name_en": letter.applicant_full_name_en,
        "applicant_citizenship_no": letter.applicant_citizenship_no,
        "letter_type": letter.letter_type.value,
    }
    data_hash = compute_data_hash(hash_payload)

    cert_id = uuid.uuid4()
    qr_path = generate_qr(cert_id)

    qr_abs_path = os.path.join("static", qr_path)
    with open(qr_abs_path, "rb") as f:
        qr_data_uri = "data:image/png;base64," + base64.b64encode(f.read()).decode()

    with open(LOGO_PATH, "rb") as f:
        logo_data_uri = "data:image/png;base64," + base64.b64encode(f.read()).decode()

    # Ward-specific images — same lookup pattern as birth cert. NOTE: the
    # signature and stamp both live on WardModel (chairperson_signature_path /
    # chairperson_stamp_path), not on the UserModel — a prior version of this
    # function looked for `chairperson.signature_path`, which does not exist
    # on UserModel, so the signature image silently never rendered.
    ward_logo_data_uri = _file_to_data_uri(ward.ward_logo_path)
    signer_signature_data_uri = _file_to_data_uri(ward.chairperson_signature_path)
    stamp_data_uri = _file_to_data_uri(ward.chairperson_stamp_path)

    ward_type_np, ward_type_en = _WARD_TYPE_LABELS.get(
        _ward_type_value(ward), ("नगरपालिका", "Municipality")
    )

    template_context = {
        "certificate_no": to_nepali_digits(certificate_no),
        "registration_date": to_nepali_digits(letter.created_at.strftime("%Y-%m-%d")),
        "issue_date": to_nepali_digits(datetime.now(timezone.utc).strftime("%Y-%m-%d")),
        "ward": ward,
        "ward_no_np": to_nepali_digits(ward.ward_no),
        "ward_type_np": ward_type_np,
        "ward_type_en": ward_type_en,
        "subject_np": subject_np,
        "subject_en": type_info["subject_en"],
        "applicant_name": letter.applicant_full_name_np,
        "applicant_citizenship_no": to_nepali_digits(letter.applicant_citizenship_no),
        "applicant_address_line": _build_applicant_address_line(
            letter.applicant_province, letter.applicant_district,
            letter.applicant_municipality, letter.applicant_ward_number,
            letter.applicant_tole,
        ),
        "clause": clause,
        "purpose": letter.purpose,
        "logo_data_uri": logo_data_uri,
        "ward_logo_data_uri": ward_logo_data_uri,
        "qr_data_uri": qr_data_uri,
        "signer_signature_data_uri": signer_signature_data_uri,
        "stamp_data_uri": stamp_data_uri,
        "signer_name": (chairperson.user_nepali_name or chairperson.user_name) if chairperson else None,
        "signer_designation_np": "वडा अध्यक्ष",
        "signer_designation_en": "Ward Chairperson",
    }

    pdf_path = render_certificate_pdf(cert_id, template_context, template_name="recommendation_certificate.html")

    certificate = RecommendationCertificateModel(
        cert_id=cert_id,
        letter_id=letter.letter_id,
        certificate_no=certificate_no,
        data_hash=data_hash,
        qr_path=qr_path,
        pdf_path=pdf_path,
        issued_by=issued_by_user_id,
    )
    db.add(certificate)
    letter.register_status = letter.register_status.__class__.CERTIFICATE_ISSUED
    db.commit()
    db.refresh(certificate)
    return certificate