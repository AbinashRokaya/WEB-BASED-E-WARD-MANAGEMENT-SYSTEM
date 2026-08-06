import hashlib
import io
import json
import os
import uuid
import random
import base64
from datetime import datetime, timezone

import qrcode
import requests
from jinja2 import Environment, FileSystemLoader
from playwright.sync_api import sync_playwright

import cloudinary.uploader
import config.cloudinary_config  # noqa: F401  (runs cloudinary.config() on import)

from model.birth_registration_model import CertificateModel
from schema.user_schema import RoleSchema

SERVICE_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_ROOT = os.path.dirname(SERVICE_DIR)   # adjust if your services/ folder is nested differently
LOGO_PATH = os.path.join(BACKEND_ROOT, "assets", "nepal-sarkar.png")  # bundled app asset, stays local

# Cloudinary "folder" prefixes — mirror what QR_DIR / PDF_DIR did locally.
CLOUDINARY_QR_FOLDER = "certificates/qr"
CLOUDINARY_PDF_FOLDER = "certificates/pdf"

VERIFY_BASE_URL = os.environ.get("VERIFY_BASE_URL", "http://localhost:5173/verify")

jinja_env = Environment(loader=FileSystemLoader("templates"))

# ── Nepali digit conversion ────────────────────────────────────────────────
_NEPALI_DIGITS = str.maketrans("0123456789", "०१२३४५६७८९")


def _build_informant_ctx(n):
    """Build the dict the template expects — same pattern as _build_parent_ctx.
    Converts citizenship/contact numbers to Nepali digits and prefers the
    Nepali name fields, so the informant block matches father/mother
    formatting instead of leaking raw English digits onto the certificate."""
    if not n:
        return None
    first = n.nominee_nepali_first_name or n.nominee_first_name
    last = n.nominee_nepali_last_name or n.nominee_last_name
    return {
        "full_name": f"{first} {last}",
        "nominee_citizenship_no": to_nepali_digits(n.nominee_citizenship_no),
        "nominee_contact_no": to_nepali_digits(n.nominee_contact_no),
        "nominee_relationship": (
            n.nominee_relationship.value if n.nominee_relationship else ""
        ),
    }


def generate_nin(db) -> str:
    """
    Locally-generated 10-digit placeholder National Identity Number.
    NOTE: this is NOT an authoritative government-issued NIN — real NINs
    come from the Department of National ID and Civil Registration, not
    a ward-level birth registration system. Treat this as a provisional
    ID until/unless the real NIN is issued and recorded separately.
    """
    while True:
        candidate = "".join(str(random.randint(0, 9)) for _ in range(10))
        exists = db.query(CertificateModel).filter(
            CertificateModel.nin_no == candidate
        ).first()
        if not exists:
            return candidate


_WARD_TYPE_LABELS = {
    "METROPOLITAN_CITY":     ("महानगरपालिका", "Metropolitan City"),
    "SUB_METROPOLITAN_CITY": ("उपमहानगरपालिका", "Sub-Metropolitan City"),
    "MUNICIPALITY":          ("नगरपालिका", "Municipality"),
    "RURAL_MUNICIPALITY":    ("गाउँपालिका", "Rural Municipality"),
}


def _ward_type_value(w) -> str:
    """Same pitfall as _parent_type_value/_role_value: ward_type is a
    SQLAlchemy Enum column holding a MunicipalityType instance."""
    return w.ward_type.value if hasattr(w.ward_type, "value") else w.ward_type


def _role_value(u) -> str:
    """Same enum-vs-string pitfall as _parent_type_value: user_role is a
    SQLAlchemy Enum column holding a RoleSchema instance, not a raw string."""
    return u.user_role.value if hasattr(u.user_role, "value") else u.user_role


def _find_chairperson(ward):
    return next(
        (u for u in ward.user if _role_value(u) == RoleSchema.WardChairperson.value),
        None,
    )


def to_nepali_digits(value) -> str:
    """Convert any value's ASCII digits to Devanagari digits for display."""
    if value is None:
        return ""
    return str(value).translate(_NEPALI_DIGITS)


def generate_certificate_no(ward_no: int, year: int, sequence: int) -> str:
    return f"BC-{ward_no}-{year}-{sequence:05d}"


def compute_data_hash(payload: dict) -> str:
    """
    Canonical, order-independent hash of the fields that appear on the
    certificate. Anyone can recompute this from the DB later to prove
    the PDF wasn't altered after issue.
    """
    canonical = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def generate_qr(cert_id: uuid.UUID) -> str:
    """
    Generates the verification QR code entirely in memory and uploads it
    to Cloudinary. Returns the full secure (https) URL — no local disk
    write, no /static mount needed for this file anymore.
    """
    verify_url = f"{VERIFY_BASE_URL}/{cert_id}"
    img = qrcode.make(verify_url)

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)

    upload_result = cloudinary.uploader.upload(
        buffer,
        public_id=f"{CLOUDINARY_QR_FOLDER}/{cert_id}",
        resource_type="image",
        overwrite=True,
    )
    return upload_result["secure_url"]


def render_certificate_pdf(cert_id: uuid.UUID, context: dict, template_name: str = "birth_certificate.html") -> str:
    """
    context must contain everything the Jinja2 template needs:
    child, father, mother, informant, address, ward, registration meta, qr_path

    template_name defaults to the birth certificate template so existing
    call sites (which only pass cert_id and context) keep working
    unchanged. Other certificate types (death, migration, ...) pass their
    own template_name explicitly.

    Playwright renders the PDF straight into memory (page.pdf() returns
    bytes when no `path` is given), and those bytes are uploaded to
    Cloudinary as a "raw" resource. Returns the secure_url — no local
    disk write, no /static mount needed for this file anymore.
    """
    template = jinja_env.get_template(template_name)
    html = template.render(**context)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.set_content(html, wait_until="networkidle")
        pdf_bytes = page.pdf(
            format="A4",
            print_background=True,
            margin={"top": "10mm", "bottom": "10mm", "left": "10mm", "right": "10mm"},
        )
        browser.close()

    upload_result = cloudinary.uploader.upload(
        io.BytesIO(pdf_bytes),
        public_id=f"{CLOUDINARY_PDF_FOLDER}/{cert_id}",
        resource_type="raw",
        overwrite=True,
    )
    return upload_result["secure_url"]


# ── helpers for the parent lookup + image embedding ────────────────────────
def _parent_type_value(p) -> str:
    """
    parent_type is a SQLAlchemy Enum column, which stores a Python enum
    instance (e.g. ParentType.FATHER), not the raw string "FATHER".
    Comparing p.parent_type == "FATHER" silently returns False unless
    ParentType subclasses (str, Enum) — so both father and mother end up
    None and every field on the certificate looks "blank". This helper
    normalizes either case to a plain string for comparison.
    """
    return p.parent_type.value if hasattr(p.parent_type, "value") else p.parent_type


def _build_parent_ctx(p):
    """Build the dict the template expects (it reads `full_name`, which
    does not exist on ParentModel — only first/last name columns do)."""
    if not p:
        return None
    first = p.parent_nepali_first_name or p.parent_first_name
    last = p.parent_nepali_last_name or p.parent_last_name
    return {
        "full_name": f"{first} {last}",
        "parent_citizenship_no": to_nepali_digits(p.parent_citizenship_no),
        "parent_occupation": p.parent_occupation,
        "parent_nationality": p.parent_nationality,
    }


def _file_to_data_uri(location, mime="image/png"):
    """
    Loads an image and returns it as a base64 data URI, for embedding into
    the offline-rendered certificate HTML (Playwright can't fetch remote
    URLs reliably inside the sandboxed render, so everything gets inlined
    up front).

    `location` may be either:
      - a full URL (http/https) — e.g. a Cloudinary secure_url, which is
        what ward_logo_path / chairperson_signature_path / qr_path etc.
        now store — fetched over HTTP.
      - a legacy path relative to the static/ mount — kept for backward
        compatibility with any records saved before the Cloudinary switch.

    Returns None (and never raises) if the asset can't be loaded, so a
    missing/unreachable image degrades to the template's placeholder
    instead of failing certificate generation.
    """
    if not location:
        return None

    try:
        if location.startswith("http://") or location.startswith("https://"):
            resp = requests.get(location, timeout=10)
            resp.raise_for_status()
            content = resp.content
        else:
            abs_path = os.path.join("static", location)
            if not os.path.exists(abs_path):
                return None
            with open(abs_path, "rb") as f:
                content = f.read()
    except Exception:
        return None

    return f"data:{mime};base64," + base64.b64encode(content).decode()


def _build_shared_address(ward, address) -> str:
    """
    Builds the combined Nepali address line shown for permanent address /
    birth place / everyone's address on the certificate.

    address.ward_nepali_name is meant to hold a tole/area name, but in
    practice it sometimes ends up holding a copy of the ward label itself
    (e.g. "वडा नं. ३") — coming from whatever picked it during registration
    (e.g. a cascading address dropdown). When that happens, appending it
    after our own "वडा नं. X" produces a visible duplicate like
    "वडा नं. ३, वडा नं. ३". This skips the tole segment in that case so
    the ward number only appears once, while still showing a genuine
    tole/area name when one is present.
    """
    ward_no_part = f"वडा नं. {to_nepali_digits(address.child_ward_number)}"
    tole = (address.ward_nepali_name or "").strip()

    parts = [
        f"{ward.ward_nepali_province} प्रदेश",
        f"{ward.ward_nepali_district} जिल्ला",
        ward.ward_nepali_municipality,
        ward_no_part,
    ]
    if tole and "वडा नं" not in tole:
        parts.append(tole)

    return ", ".join(parts)


def issue_certificate_for_registration(registration, db, issued_by_user_id):
    """
    Shared logic: builds the certificate record, QR, hash, and PDF for
    a VERIFIED registration, and flips its status to CERTIFICATE_ISSUED.
    """

    if registration.certificate:
        raise ValueError("Certificate already issued for this registration")

    ward = registration.ward
    child = registration.child

    father_row = next(
        (p for p in registration.parents if _parent_type_value(p) == "FATHER"), None
    )
    mother_row = next(
        (p for p in registration.parents if _parent_type_value(p) == "MOTHER"), None
    )

    chairperson = _find_chairperson(ward)
    informant = registration.nominees[0] if registration.nominees else None
    address = registration.address

    year = registration.created_at.year
    sequence = (
        db.query(CertificateModel)
        .filter(CertificateModel.certificate_no.like(f"BC-{ward.ward_no}-{year}-%"))
        .count()
        + 1
    )
    certificate_no = generate_certificate_no(ward.ward_no, year, sequence)
    nin_no = generate_nin(db)

    hash_payload = {
        "registration_id": str(registration.registration_id),
        "certificate_no": certificate_no,
        "nin_no": nin_no,
        "child_full_name": f"{child.child_first_name} {child.child_last_name}",
        "child_dob_ad": str(child.child_dob_ad),
        "child_gender": child.child_gender.value if child.child_gender else None,
        "father_citizenship_no": father_row.parent_citizenship_no if father_row else None,
        "mother_citizenship_no": mother_row.parent_citizenship_no if mother_row else None,
    }
    data_hash = compute_data_hash(hash_payload)

    cert_id = uuid.uuid4()
    qr_path = generate_qr(cert_id)  # now a full Cloudinary secure_url

    # qr_path is a Cloudinary URL now — _file_to_data_uri fetches it over
    # HTTP and returns a base64 data URI for embedding in the offline
    # Playwright render (also handles legacy local paths, so nothing
    # breaks for records issued before the Cloudinary switch).
    qr_data_uri = _file_to_data_uri(qr_path)

    # Embed the logo as base64, same approach as the QR — file:// paths
    # get blocked by Chromium's sandbox when Playwright renders headless.
    # This is a bundled app asset (not user data), so it stays on local disk.
    with open(LOGO_PATH, "rb") as f:
        logo_data_uri = "data:image/png;base64," + base64.b64encode(f.read()).decode()

    # Ward-specific images (uploaded per-ward in the admin router). Any of
    # these may be missing if the ward hasn't uploaded them yet — the
    # template falls back to a placeholder in that case.
    ward_logo_data_uri = _file_to_data_uri(ward.ward_logo_path)
    chairperson_signature_data_uri = _file_to_data_uri(ward.chairperson_signature_path)
    chairperson_stamp_data_uri = _file_to_data_uri(ward.chairperson_stamp_path)

    ward_type_np, ward_type_en = _WARD_TYPE_LABELS.get(
        _ward_type_value(ward), ("नगरपालिका", "Municipality")
    )

    informant_ctx = _build_informant_ctx(informant)

    template_context = {
        "certificate_no": to_nepali_digits(certificate_no),
        "registration_date": to_nepali_digits(registration.created_at.strftime("%Y-%m-%d")),
        "issue_date": to_nepali_digits(datetime.now(timezone.utc).strftime("%Y-%m-%d")),
        "nin": to_nepali_digits(nin_no),
        "ward": ward,
        "ward_no_np": to_nepali_digits(ward.ward_no),
        "ward_type_np": ward_type_np,
        "ward_type_en": ward_type_en,
        "child": {
            "full_name": f"{child.child_nepali_first_name} {child.child_nepali_last_name}",
            "dob_bs": to_nepali_digits(child.child_dob_bs.strftime("%Y-%m-%d")) if child.child_dob_bs else "",
            "dob_ad": to_nepali_digits(child.child_dob_ad.strftime("%Y-%m-%d")) if child.child_dob_ad else "",
            "gender_label": {"MALE": "पुरुष", "FEMALE": "महिला", "OTHER": "अन्य"}.get(
                child.child_gender.value if child.child_gender else "", ""
            ),
            "birth_place_label": {"HOME": "घरमा", "HOSPITAL": "स्वास्थ्य संस्था", "OTHER": "अन्य"}.get(
                child.child_birth_place.value if child.child_birth_place else "", ""
            ),
            "birth_kind_label": {"SINGLE": "एकल", "TWIN": "जुडुवा", "TRIPLET_OR_MORE": "तेस्रो वा बढी"}.get(
                child.child_birth_kind.value if child.child_birth_kind else "", ""
            ),
        },
        "father": _build_parent_ctx(father_row),
        "mother": _build_parent_ctx(mother_row),
        "informant": informant_ctx,
        "shared_address": _build_shared_address(ward, address),
        "logo_data_uri": logo_data_uri,
        "ward_logo_data_uri": ward_logo_data_uri,
        "chairperson_signature_data_uri": chairperson_signature_data_uri,
        "chairperson_stamp_data_uri": chairperson_stamp_data_uri,
        "qr_data_uri": qr_data_uri,
        "registrar_name": (
            (chairperson.user_nepali_name or chairperson.user_name)
            if chairperson else None
        ),
        "registrar_designation": "वडा अध्यक्ष" if chairperson else None,
    }

    pdf_path = render_certificate_pdf(cert_id, template_context)

    certificate = CertificateModel(
        cert_id=cert_id,
        registration_id=registration.registration_id,
        certificate_no=certificate_no,
        nin_no=nin_no,
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