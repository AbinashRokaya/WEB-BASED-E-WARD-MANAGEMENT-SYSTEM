"""
reverse_cloudinary_to_static.py

Reverses migrate_static_to_cloudinary.py: walks every model/field that
currently holds a Cloudinary secure_url and downloads it back into the
local static/ folder structure the app originally used, rewriting the
DB column back to the old relative path.

Safe to re-run — any column that's already a local relative path (not
starting with http/https) is skipped.

Run once, from your backend root, with your normal environment loaded:

    python reverse_cloudinary_to_static.py

Requires `requests` (pip install requests --break-system-packages).
"""
import os
import sys
import uuid
import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.db import SessionLocal

from model.birth_registration_model import BirthRegistrationModel, CertificateModel
from model.death_registration_model import DeathRegistrationModel, DeathCertificateModel
from model.migration_registration_model import MigrationRegistrationModel, MigrationCertificateModel
from model.recommendation_model import RecommendationLetterModel, RecommendationCertificateModel
from model.notice_model import NoticeModel
from model.complaint_model import ComplaintModel
from model.ward_model import WardModel
from model.tax_model import TaxReceiptModel


def _is_cloud_url(value) -> bool:
    return bool(value) and str(value).startswith(("http://", "https://"))


def _guess_ext(url: str, content_type: str) -> str:
    path_ext = os.path.splitext(url.split("?")[0])[1]
    if path_ext and len(path_ext) <= 5:
        return path_ext
    mapping = {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/webp": ".webp",
        "application/pdf": ".pdf",
        "application/msword": ".doc",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    }
    return mapping.get(content_type, "")


def _download_to_static(url: str, rel_dir: str, suffix: str) -> str | None:
    """Downloads url, saves under static/<rel_dir>/<suffix>_<uuid><ext>,
    returns the path relative to the static/ mount (what the DB column
    used to store before the Cloudinary migration), or None on failure."""
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        print(f"  FAILED download {url}: {e}")
        return None

    ext = _guess_ext(url, resp.headers.get("Content-Type", ""))
    filename = f"{suffix}_{uuid.uuid4().hex[:8]}{ext}"
    local_dir = os.path.join("static", rel_dir)
    os.makedirs(local_dir, exist_ok=True)
    local_path = os.path.join(local_dir, filename)

    with open(local_path, "wb") as f:
        f.write(resp.content)

    return f"{rel_dir}/{filename}"


def _revert_field(row, field_name: str, rel_dir: str, suffix: str) -> bool:
    value = getattr(row, field_name, None)
    if not _is_cloud_url(value):
        return False

    rel_path = _download_to_static(value, rel_dir, suffix)
    if not rel_path:
        return False

    setattr(row, field_name, rel_path)
    print(f"  reverted {field_name}: {value} -> {rel_path}")
    return True


DOCUMENT_REVERSALS = [
    (
        BirthRegistrationModel,
        lambda r: f"birth_registration/{r.registration_id}",
        [
            "father_citizenship_front_path", "father_citizenship_back_path",
            "mother_citizenship_front_path", "mother_citizenship_back_path",
            "hospital_birth_certificate_path", "vaccination_card_path",
        ],
    ),
    (
        DeathRegistrationModel,
        lambda r: f"death_registration/{r.registration_id}",
        [
            "deceased_citizenship_front_path", "deceased_citizenship_back_path",
            "informant_citizenship_front_path", "informant_citizenship_back_path",
            "hospital_death_report_path", "police_report_path",
        ],
    ),
    (
        MigrationRegistrationModel,
        lambda r: f"migration_registration/{r.migration_id}",
        [
            "applicant_citizenship_front_path", "applicant_citizenship_back_path",
            "address_proof_path", "destination_proof_path", "applicant_photo_path",
        ],
    ),
    (
        RecommendationLetterModel,
        lambda r: f"recommendation_letter/{r.letter_id}",
        [
            "applicant_citizenship_front_path", "applicant_citizenship_back_path",
            "supporting_document_path",
        ],
    ),
    (
        NoticeModel,
        lambda r: f"notices/{r.notice_id}",
        ["notice_attachment_path"],
    ),
    (
        ComplaintModel,
        lambda r: f"complaint/{r.complaint_id}",
        ["attachment_1_path", "attachment_2_path", "attachment_3_path"],
    ),
    (
        WardModel,
        lambda r: f"wards/{r.ward_id}",
        ["ward_logo_path", "chairperson_signature_path", "chairperson_stamp_path"],
    ),
]

PDF_REVERSALS = [
    (CertificateModel, "certificates/pdf"),
    (DeathCertificateModel, "certificates/pdf"),
    (MigrationCertificateModel, "certificates/pdf"),
    (RecommendationCertificateModel, "certificates/pdf"),
    (TaxReceiptModel, "tax_receipts/pdf"),
]
QR_REVERSALS = [
    (CertificateModel, "certificates/qr"),
    (DeathCertificateModel, "certificates/qr"),
    (MigrationCertificateModel, "certificates/qr"),
    (RecommendationCertificateModel, "certificates/qr"),
    (TaxReceiptModel, "tax_receipts/qr"),
]


def run():
    db = SessionLocal()
    changed = 0
    try:
        for model, folder_fn, fields in DOCUMENT_REVERSALS:
            rows = db.query(model).all()
            print(f"\n{model.__name__}: {len(rows)} row(s)")
            for row in rows:
                rel_dir = folder_fn(row)
                for field in fields:
                    if _revert_field(row, field, rel_dir, suffix=field.replace("_path", "")):
                        changed += 1

        for model, folder in PDF_REVERSALS:
            rows = db.query(model).all()
            print(f"\n{model.__name__} (pdf_path): {len(rows)} row(s)")
            for row in rows:
                if _revert_field(row, "pdf_path", folder, suffix="cert"):
                    changed += 1

        for model, folder in QR_REVERSALS:
            rows = db.query(model).all()
            print(f"\n{model.__name__} (qr_path): {len(rows)} row(s)")
            for row in rows:
                if _revert_field(row, "qr_path", folder, suffix="qr"):
                    changed += 1

        db.commit()
        print(f"\nDone. {changed} row(s) reverted.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run()