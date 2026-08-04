"""
Issues the payment receipt PDF the moment a tax payment completes — same
mechanics as birth_registration_service.issue_certificate_for_registration
(hash + QR + Jinja2->Playwright PDF), but the trigger is a completed
payment instead of a chairperson approval, since a tax receipt has no
review chain: there's nothing to issue until the money has landed.

The receipt artifact (hash/QR/PDF) now lives in its own TaxReceiptModel
row, one-to-one with TaxPaymentModel — same split as CertificateModel
from BirthRegistrationModel. payment.pdf_path / payment.qr_path /
payment.data_hash / payment.receipt_issued_at still work everywhere
else in the codebase via read-only proxy properties on TaxPaymentModel
itself, so this file is the only place that needs to know receipts are
now a separate table.
"""
import base64
import hashlib
import json
import os
from datetime import datetime, timezone

import qrcode
from jinja2 import Environment, FileSystemLoader
from playwright.sync_api import sync_playwright

from model.tax_model import TaxPaymentModel, TaxAssessmentModel, TaxReceiptModel

BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGO_PATH = os.path.join(BACKEND_ROOT, "assets", "nepal-sarkar.png")

QR_DIR = "static/tax_receipts/qr"
PDF_DIR = "static/tax_receipts/pdf"
VERIFY_BASE_URL = os.environ.get("TAX_VERIFY_BASE_URL", "http://localhost:5173/verify-tax-receipt")

os.makedirs(QR_DIR, exist_ok=True)
os.makedirs(PDF_DIR, exist_ok=True)

jinja_env = Environment(loader=FileSystemLoader("templates"))

_NEPALI_DIGITS = str.maketrans("0123456789", "०१२३४५६७८९")
_TAX_TYPE_LABELS_NP = {
    "PROPERTY": "एकीकृत सम्पत्ति कर",
    "HOUSE_RENT": "घर बहाल कर",
    "BUSINESS": "व्यवसाय कर",
}


def to_nepali_digits(value) -> str:
    if value is None:
        return ""
    return str(value).translate(_NEPALI_DIGITS)


def _file_to_data_uri(rel_path, mime="image/png"):
    """rel_path is relative to the static/ mount, e.g. wards/{id}/stamp_xxx.png"""
    if not rel_path:
        return None
    abs_path = os.path.join("static", rel_path)
    if not os.path.exists(abs_path):
        return None
    with open(abs_path, "rb") as f:
        return f"data:{mime};base64," + base64.b64encode(f.read()).decode()


def compute_data_hash(payload: dict) -> str:
    """
    Canonical, order-independent hash of the fields that appear on the
    receipt. Anyone can recompute this from the DB later to prove the
    PDF wasn't altered after issue — same approach as the birth
    certificate's data_hash.
    """
    canonical = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def generate_qr(payment_id) -> str:
    verify_url = f"{VERIFY_BASE_URL}/{payment_id}"
    img = qrcode.make(verify_url)
    filename = f"{payment_id}.png"
    filepath = os.path.join(QR_DIR, filename)
    img.save(filepath)
    return f"tax_receipts/qr/{filename}"  # relative to /static mount


def render_receipt_pdf(payment_id, context: dict) -> str:
    template = jinja_env.get_template("tax_receipt.html")
    html = template.render(**context)

    filename = f"{payment_id}.pdf"
    filepath = os.path.join(PDF_DIR, filename)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.set_content(html, wait_until="networkidle")
        page.pdf(
            path=filepath,
            format="A4",
            print_background=True,
            margin={"top": "10mm", "bottom": "10mm", "left": "10mm", "right": "10mm"},
        )
        browser.close()

    return f"tax_receipts/pdf/{filename}"  # relative to /static mount


def issue_tax_receipt(db, payment: TaxPaymentModel, issued_by_user_id=None) -> TaxPaymentModel:
    """
    Called right after a payment flips its assessment to PAID — from both
    the manual/CASH path (record_tax_payment) and the Khalti callback
    (verify_khalti_tax_payment). Idempotent: if a TaxReceiptModel row
    already exists for this payment, returns the payment as-is instead
    of regenerating — this matters because the Khalti verify endpoint
    can legitimately be hit more than once for the same pidx (browser
    back button, retried callback), and that must not mint a second
    receipt / overwrite the hash of one already handed to the citizen.
    payment_id is unique on TaxReceiptModel, so a second insert would
    also fail at the DB level as a backstop.
    """
    if payment.receipt:
        return payment

    assessment = db.query(TaxAssessmentModel).filter(
        TaxAssessmentModel.id == payment.assessment_id
    ).first()
    if not assessment:
        raise ValueError("Assessment not found for this payment")

    citizen = assessment.citizen
    ward = assessment.ward

    hash_payload = {
        "payment_id": str(payment.id),
        "assessment_id": str(assessment.id),
        "receipt_no": payment.receipt_no,
        "amount_paid": str(payment.amount_paid),
        "method": payment.method.value,
        "citizen_id": assessment.citizen_id,
        "fiscal_year": assessment.fiscal_year,
    }
    data_hash = compute_data_hash(hash_payload)

    qr_path = generate_qr(payment.id)
    qr_data_uri = _file_to_data_uri(qr_path)

    with open(LOGO_PATH, "rb") as f:
        logo_data_uri = "data:image/png;base64," + base64.b64encode(f.read()).decode()

    # Reuses the ward's chairperson stamp as the receipt watermark —
    # same asset the birth certificate uses. The system has no separate
    # "revenue officer stamp" upload anywhere; swap this for a dedicated
    # field later if you add one to WardModel.
    ward_stamp_data_uri = _file_to_data_uri(getattr(ward, "chairperson_stamp_path", None))

    template_context = {
        "receipt_no": payment.receipt_no,
        "paid_date": to_nepali_digits(payment.paid_at.strftime("%Y-%m-%d")) if payment.paid_at else "",
        "tax_type_label": _TAX_TYPE_LABELS_NP.get(assessment.tax_type.value, assessment.tax_type.value),
        "fiscal_year": assessment.fiscal_year,
        "citizen_name": (citizen.user_nepali_name or citizen.user_name) if citizen else "",
        "ward": ward,
        "ward_no_np": to_nepali_digits(ward.ward_no) if ward else "",
        "base_amount": to_nepali_digits(f"{assessment.base_amount:,.2f}"),
        "penalty_amount": to_nepali_digits(f"{assessment.penalty_amount:,.2f}"),
        "discount_amount": to_nepali_digits(f"{assessment.discount_amount:,.2f}"),
        "total_due": to_nepali_digits(f"{assessment.total_due:,.2f}"),
        "amount_paid": to_nepali_digits(f"{payment.amount_paid:,.2f}"),
        "method_label": payment.method.value,
        "transaction_id": payment.transaction_id or "",
        "logo_data_uri": logo_data_uri,
        "ward_stamp_data_uri": ward_stamp_data_uri,
        "qr_data_uri": qr_data_uri,
    }

    pdf_path = render_receipt_pdf(payment.id, template_context)

    receipt = TaxReceiptModel(
        payment_id=payment.id,
        data_hash=data_hash,
        qr_path=qr_path,
        pdf_path=pdf_path,
        issued_by=issued_by_user_id,
    )
    db.add(receipt)
    db.commit()
    db.refresh(payment)
    return payment