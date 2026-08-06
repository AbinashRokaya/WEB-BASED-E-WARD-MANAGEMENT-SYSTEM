import uuid
import base64
from datetime import datetime, timezone

from model.death_registration_model import DeathCertificateModel
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


def generate_death_certificate_no(ward_no: int, year: int, sequence: int) -> str:
    return f"DC-{ward_no}-{year}-{sequence:05d}"


def _find_death_signing_officer(ward):
    """
    Death certificates are signed by the Ward Chairperson — checked first,
    same as birth and migration — falling back to the Ward Secretary only
    if no chairperson is on record for the ward.
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


def _build_death_address_line(province, district, municipality, ward_number, tole):
    parts = [
        p for p in [
            f"{province} जिल्ला" if province else None,
            municipality,
            f"वडा नं. {to_nepali_digits(ward_number)}" if ward_number else None,
            tole,
        ] if p
    ]
    return ", ".join(parts)


def issue_certificate_for_death_registration(registration, db, issued_by_user_id):
    """
    Same shape as certificate_service.issue_certificate_for_registration,
    adapted for death registrations: builds the certificate record, QR,
    hash, and PDF for a VERIFIED death registration, and flips its status
    to CERTIFICATE_ISSUED.
    """

    if registration.certificate:
        raise ValueError("Certificate already issued for this registration")

    ward = registration.ward
    deceased = registration.deceased
    death_detail = registration.death_detail
    informant = registration.informant
    address = registration.address  # DeathAddressModel

    signer, designation_np, designation_en = _find_death_signing_officer(ward)

    year = registration.created_at.year
    sequence = (
        db.query(DeathCertificateModel)
        .filter(DeathCertificateModel.certificate_no.like(f"DC-{ward.ward_no}-{year}-%"))
        .count()
        + 1
    )
    certificate_no = generate_death_certificate_no(ward.ward_no, year, sequence)

    deceased_full_name = " ".join(
        filter(None, [
            deceased.deceased_nepali_first_name or deceased.deceased_first_name,
            deceased.deceased_nepali_last_name or deceased.deceased_last_name,
        ])
    )

    hash_payload = {
        "registration_id": str(registration.registration_id),
        "certificate_no": certificate_no,
        "deceased_full_name": deceased_full_name,
        "death_date_bs": str(death_detail.death_date_bs) if death_detail.death_date_bs else None,
        "deceased_citizenship_no": deceased.deceased_citizenship_no,
    }
    data_hash = compute_data_hash(hash_payload)

    cert_id = uuid.uuid4()
    qr_path = generate_qr(cert_id)  # now a full Cloudinary secure_url

    # qr_path is a Cloudinary URL now — _file_to_data_uri fetches it over
    # HTTP and returns a base64 data URI for embedding in the offline
    # Playwright render (also handles legacy local paths, so nothing
    # breaks for records issued before the Cloudinary switch).
    qr_data_uri = _file_to_data_uri(qr_path)

    with open(LOGO_PATH, "rb") as f:
        logo_data_uri = "data:image/png;base64," + base64.b64encode(f.read()).decode()

    signer_signature_data_uri = _file_to_data_uri(
        getattr(signer, "signature_path", None)
    ) if signer else None
    stamp_data_uri = _file_to_data_uri(ward.chairperson_stamp_path)

    template_context = {
        "certificate_no": to_nepali_digits(certificate_no),
        "registration_date": to_nepali_digits(registration.created_at.strftime("%Y-%m-%d")),
        "issue_date": to_nepali_digits(datetime.now(timezone.utc).strftime("%Y-%m-%d")),
        "ward": ward,
        "ward_no_np": to_nepali_digits(ward.ward_no),
        "deceased": {
            "full_name": deceased_full_name,
            "gender": deceased.deceased_gender.value if deceased.deceased_gender else None,
            "dob_bs": to_nepali_digits(deceased.deceased_dob_bs.strftime("%Y-%m-%d")) if deceased.deceased_dob_bs else "",
            "dob_ad": to_nepali_digits(deceased.deceased_dob_ad.strftime("%Y-%m-%d")) if deceased.deceased_dob_ad else "",
            "birth_place": None,  # not collected on this form's DeceasedModel
        },
        "death_detail": {
            "death_date_bs": to_nepali_digits(death_detail.death_date_bs.strftime("%Y-%m-%d")) if death_detail.death_date_bs else "",
            "death_time": to_nepali_digits(death_detail.death_time) if death_detail.death_time else "",
            "death_place_type": death_detail.death_place_type.value if death_detail.death_place_type else None,
            "death_cause": death_detail.death_cause,
        },
        "deceased_address": {
            "province": address.deceased_province,
            "district": address.deceased_district,
            "municipality": address.deceased_municipality,
            "ward_number": to_nepali_digits(address.deceased_ward_number),
            "tole": address.deceased_tole,
        },
        "death_place_address_line": _build_death_address_line(
            address.death_place_province, address.death_place_district,
            address.death_place_municipality, address.death_place_ward_number,
            address.death_place_tole,
        ),
        "informant": {
            "informant_name": informant.informant_name if informant else "",
            "informant_relationship": (
                informant.informant_relationship.value
                if informant and informant.informant_relationship else ""
            ),
        },
        "informant_address_line": _build_death_address_line(
            address.informant_province, address.informant_district,
            address.informant_municipality, address.informant_ward_number,
            address.informant_tole,
        ),
        "logo_data_uri": logo_data_uri,
        "qr_data_uri": qr_data_uri,
        "signer_signature_data_uri": signer_signature_data_uri,
        "stamp_data_uri": stamp_data_uri,
        "signer_name": (signer.user_nepali_name or signer.user_name) if signer else None,
        "signer_designation_np": designation_np,
        "signer_designation_en": designation_en,
    }

    pdf_path = render_certificate_pdf(cert_id, template_context, template_name="death_certificate.html")

    certificate = DeathCertificateModel(
        cert_id=cert_id,
        registration_id=registration.registration_id,
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