import os
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger(__name__)

SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", 587))
SMTP_USER = os.environ.get("SMTP_USER")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD")
FROM_EMAIL = os.environ.get("FROM_EMAIL", SMTP_USER)


def _send_email(to_email: str, subject: str, body: str, context: str):
    """Shared send logic with visible error logging instead of silent failure."""
    if not SMTP_USER or not SMTP_PASSWORD:
        logger.error(
            f"[{context}] SMTP_USER/SMTP_PASSWORD not set — cannot send email to {to_email}"
        )
        return

    msg = MIMEMultipart()
    msg["From"] = FROM_EMAIL
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(FROM_EMAIL, to_email, msg.as_string())
        logger.info(f"[{context}] Email sent to {to_email}")
    except smtplib.SMTPAuthenticationError as e:
        logger.error(
            f"[{context}] SMTP auth failed for {SMTP_USER}. "
            f"If using Gmail, you need an App Password (not your regular password) "
            f"and 2FA must be enabled. Error: {e}"
        )
    except smtplib.SMTPException as e:
        logger.error(f"[{context}] SMTP error sending to {to_email}: {e}")
    except Exception as e:
        logger.error(f"[{context}] Unexpected error sending to {to_email}: {e}")


def send_certificate_ready_email(to_email: str, child_full_name: str, certificate_no: str, download_url: str):
    if not to_email:
        logger.warning("send_certificate_ready_email: no email on file — skipping")
        return  # no email on file — skip silently, don't break certificate issuance

    subject = "Birth Certificate Issued / जन्म दर्ता प्रमाणपत्र जारी भयो"
    body = f"""Dear User,

The birth certificate for {child_full_name} has been issued.

Certificate No: {certificate_no}
Download: {download_url}

This is an automated notification from the Birth Registration System.
"""
    _send_email(to_email, subject, body, context="certificate_ready")


def send_registration_rejected_email(to_email: str, user_name: str, ward_name: str = ""):
    if not to_email:
        logger.warning("send_registration_rejected_email: no email on file — skipping")
        return  # no email on file — skip silently

    subject = "Registration Not Approved / दर्ता स्वीकृत भएन"
    ward_line = f" for {ward_name}" if ward_name else ""
    body = f"""Dear {user_name},

Your registration{ward_line} could not be approved. This is usually because \
the citizenship or address details provided do not match this ward's records.

If you believe this is a mistake, please visit your ward office with your \
citizenship certificate for verification, or contact them directly.

This is an automated notification from the Birth Registration System.
"""
    _send_email(to_email, subject, body, context="registration_rejected")

# services/email_service.py — add this function

def send_recommendation_certificate_ready_email(to_email: str, applicant_full_name: str, certificate_no: str, download_url: str):
    if not to_email:
        logger.warning("send_recommendation_certificate_ready_email: no email on file — skipping")
        return

    subject = "Recommendation Letter Issued / सिफारिस पत्र जारी भयो"
    body = f"""Dear User,

The recommendation letter for {applicant_full_name} has been issued.

Certificate No: {certificate_no}
Download: {download_url}

This is an automated notification from the Recommendation Letter System.
"""
    _send_email(to_email, subject, body, context="recommendation_certificate_ready")