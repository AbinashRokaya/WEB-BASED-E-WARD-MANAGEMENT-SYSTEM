# services/email_service.py
"""
Low-level email sending. Knows about SMTP and message bodies — nothing else.

It does NOT know what a certificate is, which model holds the applicant, or
how to build a download URL. That belongs to services/notification_service.py.
Keeping the split means adding a 5th document type touches one dict, not a
5th near-identical send_*_email function.
"""
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from config import settings

logger = logging.getLogger(__name__)


def _send_email(to_email: str, subject: str, body: str, context: str) -> bool:
    """
    Send one plain-text email. Returns True on success, False on failure.

    Never raises: this is called from a BackgroundTask after a certificate is
    already committed to the database. An SMTP outage must not turn a
    successfully issued certificate into a 500 for the ward chairperson.
    Every failure path logs the reason instead of failing silently.
    """
    if not to_email:
        logger.warning(f"[{context}] no recipient email address — skipping send")
        return False

    # Read config at CALL time, not import time. See config/settings.py.
    if not settings.smtp_is_configured():
        logger.error(
            f"[{context}] SMTP_USER / SMTP_PASSWORD are not set — "
            f"cannot send email to {to_email}. Check your .env file."
        )
        return False

    msg = MIMEMultipart()
    msg["From"] = settings.FROM_EMAIL
    msg["To"] = to_email
    msg["Subject"] = subject
    # utf-8 is required — these bodies contain Devanagari.
    msg.attach(MIMEText(body, "plain", "utf-8"))

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as server:
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(settings.FROM_EMAIL, to_email, msg.as_string())
        logger.info(f"[{context}] email sent to {to_email}")
        return True

    except smtplib.SMTPAuthenticationError as e:
        logger.error(
            f"[{context}] SMTP authentication failed for {settings.SMTP_USER}. "
            f"For Gmail you must use a 16-character App Password (with 2FA "
            f"enabled on the account), not the normal account password. Error: {e}"
        )
    except smtplib.SMTPRecipientsRefused as e:
        logger.error(f"[{context}] recipient refused: {to_email} — {e}")
    except smtplib.SMTPException as e:
        logger.error(f"[{context}] SMTP error sending to {to_email}: {e}")
    except OSError as e:
        # Covers connection refused / DNS failure / timeout.
        logger.error(f"[{context}] network error reaching {settings.SMTP_HOST}: {e}")
    except Exception as e:
        logger.exception(f"[{context}] unexpected error sending to {to_email}: {e}")

    return False


def send_certificate_ready_email(
    to_email: str,
    subject_name: str,
    certificate_no: str,
    download_url: str,
    label_en: str = "Certificate",
    label_np: str = "प्रमाणपत्र",
    recipient_name: str = "",
) -> bool:
    """
    'Your certificate is ready' — one function for EVERY document type.

    Replaces the old send_certificate_ready_email + the near-duplicate
    send_recommendation_certificate_ready_email. The document type is data
    (label_en / label_np), not a separate function.

    subject_name   — who the certificate is ABOUT (child, deceased, applicant)
    recipient_name — who the email is going TO (the citizen who applied)
    """
    greeting = f"Dear {recipient_name}," if recipient_name else "Dear Citizen,"
    subject = f"{label_en} Issued / {label_np} जारी भयो"
    body = f"""{greeting}

The {label_en.lower()} for {subject_name} has been issued.

Certificate No : {certificate_no}
Download       : {download_url}

You can also view and download it any time by logging in to the e-Ward portal.

This is an automated message from the e-Ward Management System.
Please do not reply to this email.

--
ई-वडा व्यवस्थापन प्रणाली
"""
    return _send_email(to_email, subject, body, context=f"cert_ready:{label_en}")


def send_registration_rejected_email(
    to_email: str,
    user_name: str,
    ward_name: str = "",
) -> bool:
    """Sent when a citizen's account registration is not approved."""
    ward_line = f" for {ward_name}" if ward_name else ""
    subject = "Registration Not Approved / दर्ता स्वीकृत भएन"
    body = f"""Dear {user_name},

Your registration{ward_line} could not be approved. This is usually because the
citizenship or address details provided do not match this ward's records.

If you believe this is a mistake, please visit your ward office with your
citizenship certificate for verification, or contact the office directly.

This is an automated message from the e-Ward Management System.
Please do not reply to this email.

--
ई-वडा व्यवस्थापन प्रणाली
"""
    return _send_email(to_email, subject, body, context="registration_rejected")