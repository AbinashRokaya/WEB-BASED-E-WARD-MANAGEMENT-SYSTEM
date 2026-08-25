# services/notification_service.py
"""
Certificate notification dispatch — ONE place that knows how to tell a
citizen their document is ready.

THE BUG THIS FIXES
------------------
Certificates were being issued through two different code paths:

  A) POST /v1/<type>-registration/{id}/issue-certificate   → emailed
  B) POST /v1/ward-chairperson/.../approve                 → DID NOT email

Path B is the one the chairperson dashboard actually uses. It called
issue_certificate_for_*() directly, so the PDF was generated and the status
flipped to CERTIFICATE_ISSUED, but no email was ever queued. It looked like
broken SMTP config; the email was simply never sent.

On top of that, path A repeated ~20 lines of "find the applicant, read their
email, build the URL, add_task, log three different warnings" in four routers,
each subtly different (the recommendation one logged nothing at all).

Both problems are the same problem: no single owner. This module is that owner.
"""
import logging

from fastapi import BackgroundTasks

from config import settings
from services.email_service import send_certificate_ready_email

logger = logging.getLogger(__name__)


# Everything that differs between document types lives HERE, as data.
# Adding a new certificate type = add one entry. No new function, no new
# router code, no new email template.
#
#   prefix       — the router prefix that owns /{id}/certificate/download
#   id_attr      — the primary key attribute name on the record model
#   subject_name — who the certificate is ABOUT (callable on the record)
CERTIFICATE_KINDS = {
    "birth": {
        "label_en": "Birth Certificate",
        "label_np": "जन्म दर्ता प्रमाणपत्र",
        "prefix": "/v1/birth-registration",
        "id_attr": "registration_id",
        "subject_name": lambda r: f"{r.child.child_first_name} {r.child.child_last_name}",
    },
    "death": {
        "label_en": "Death Certificate",
        "label_np": "मृत्यु दर्ता प्रमाणपत्र",
        "prefix": "/v1/death-registration",
        "id_attr": "registration_id",
        "subject_name": lambda r: f"{r.deceased.deceased_first_name} {r.deceased.deceased_last_name}",
    },
    "migration": {
        "label_en": "Migration Certificate",
        "label_np": "बसाइँसराइ प्रमाणपत्र",
        "prefix": "/v1/migration-registration",
        "id_attr": "migration_id",
        "subject_name": lambda r: r.applicant.applicant_full_name_en,
    },
    "recommendation": {
        "label_en": "Recommendation Letter",
        "label_np": "सिफारिस पत्र",
        "prefix": "/v1/recommendation-letter",
        "id_attr": "letter_id",
        "subject_name": lambda r: r.applicant_full_name_en,
    },
}


def build_download_url(kind: str, record) -> str:
    """Absolute, externally reachable download URL for this record's certificate."""
    cfg = CERTIFICATE_KINDS[kind]
    record_id = getattr(record, cfg["id_attr"])
    return f"{settings.BACKEND_BASE_URL}{cfg['prefix']}/{record_id}/certificate/download"


def notify_certificate_issued(
    background_tasks: BackgroundTasks,
    kind: str,
    record,
    certificate,
) -> bool:
    """
    Queue the "your certificate is ready" email to the citizen who applied.

    `record.submitted_by_user` IS the citizen — registrations are submitted by
    the citizen's own account, so their user_email is the correct recipient.

    Returns True if an email was queued, False otherwise. Callers should put
    this in the response as `notification_sent` so the chairperson can SEE
    that a citizen was unreachable instead of assuming delivery.

    Never raises. A notification problem must not roll back an already-issued
    certificate — every failure is logged with the reason and swallowed.
    """
    cfg = CERTIFICATE_KINDS.get(kind)
    if cfg is None:
        logger.error(f"notify_certificate_issued: unknown certificate kind '{kind}'")
        return False

    cert_no = getattr(certificate, "certificate_no", "<unknown>")

    try:
        applicant = record.submitted_by_user
    except Exception as e:
        logger.error(f"[{kind}] {cert_no}: could not load submitted_by_user: {e}")
        return False

    if applicant is None:
        logger.warning(
            f"[{kind}] certificate {cert_no} issued, but submitted_by_user is "
            f"missing on the record — no email sent."
        )
        return False

    to_email = getattr(applicant, "user_email", None)
    if not to_email:
        logger.warning(
            f"[{kind}] certificate {cert_no} issued, but user "
            f"{getattr(applicant, 'user_id', '?')} has no user_email on file — "
            f"no email sent."
        )
        return False

    try:
        subject_name = cfg["subject_name"](record)
    except Exception as e:
        # A missing child/deceased/applicant relation shouldn't block the email.
        logger.error(f"[{kind}] {cert_no}: could not resolve subject name: {e}")
        subject_name = "the applicant"

    background_tasks.add_task(
        send_certificate_ready_email,
        to_email,
        subject_name,
        cert_no,
        build_download_url(kind, record),
        cfg["label_en"],
        cfg["label_np"],
        getattr(applicant, "user_name", "") or "",
    )
    logger.info(f"[{kind}] certificate email queued for {to_email} (cert {cert_no})")
    return True