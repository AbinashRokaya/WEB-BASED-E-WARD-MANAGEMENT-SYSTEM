"""
migrate_static_to_cloudinary.py

One-off script: walks every model that stores a document/image/PDF path
and, for any value that's still a local relative static/ path (not yet a
full http(s) Cloudinary URL), uploads the local file to Cloudinary and
rewrites the DB column to the new secure_url.

Safe to re-run — any column that's already a full URL is skipped, so a
second run after a partial failure just picks up where it left off.

Run once, from your backend root, with your normal environment loaded
(same DATABASE_URL / CLOUD_NAME / API_KEY / API_SECRET as the app):

    python migrate_static_to_cloudinary.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Adjust this import to match whichever session factory your app actually
# uses — some of your routers import get_db from database.db, others from
# database.database. Point this at the same one your app uses.
from database.db import SessionLocal

from utils.cloud_storage import upload_local_file

from model.birth_registration_model import BirthRegistrationModel, CertificateModel
from model.death_registration_model import DeathRegistrationModel, DeathCertificateModel
from model.migration_registration_model import MigrationRegistrationModel, MigrationCertificateModel
from model.recommendation_model import RecommendationLetterModel, RecommendationCertificateModel
from model.notice_model import NoticeModel
from model.complaint_model import ComplaintModel
from model.ward_model import WardModel
from model.tax_model import TaxReceiptModel


def _is_local_path(value) -> bool:
    return bool(value) and not str(value).startswith(("http://", "https://"))


def _migrate_field(row, field_name: str, folder: str, resource_type: str = "image") -> bool:
    value = getattr(row, field_name, None)
    if not _is_local_path(value):
        return False

    local_path = os.path.join("static", value)
    if not os.path.exists(local_path):
        print(f"  SKIP {field_name}: local file missing at {local_path}")
        return False

    public_id = os.path.splitext(os.path.basename(value))[0]
    try:
        url = upload_local_file(local_path, folder=folder, public_id=public_id, resource_type=resource_type)
    except Exception as e:
        print(f"  FAILED {field_name} ({local_path}): {e}")
        return False

    setattr(row, field_name, url)
    print(f"  migrated {field_name}: {value} -> {url}")
    return True


# (model, folder-per-row, [field names]) — folder mirrors the same
# per-record grouping the live upload endpoints already use, so migrated
# files land in the same Cloudinary folder a fresh upload would.
DOCUMENT_MIGRATIONS = [
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

# Certificate/receipt PDFs and QR codes live in fixed folders (not grouped
# by parent record) — same as the live generate_qr()/render_certificate_pdf()
# calls already use.
PDF_MIGRATIONS = [
    (CertificateModel, "certificates/pdf"),
    (DeathCertificateModel, "certificates/pdf"),
    (MigrationCertificateModel, "certificates/pdf"),
    (RecommendationCertificateModel, "certificates/pdf"),
    (TaxReceiptModel, "tax_receipts/pdf"),
]
QR_MIGRATIONS = [
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
        for model, folder_fn, fields in DOCUMENT_MIGRATIONS:
            rows = db.query(model).all()
            print(f"\n{model.__name__}: {len(rows)} row(s)")
            for row in rows:
                folder = folder_fn(row)
                if any(_migrate_field(row, field, folder) for field in fields):
                    changed += 1

        for model, folder in PDF_MIGRATIONS:
            rows = db.query(model).all()
            print(f"\n{model.__name__} (pdf_path): {len(rows)} row(s)")
            for row in rows:
                if _migrate_field(row, "pdf_path", folder):
                    changed += 1

        for model, folder in QR_MIGRATIONS:
            rows = db.query(model).all()
            print(f"\n{model.__name__} (qr_path): {len(rows)} row(s)")
            for row in rows:
                if _migrate_field(row, "qr_path", folder):
                    changed += 1

        db.commit()
        print(f"\nDone. {changed} row(s) updated.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run()