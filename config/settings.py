# config/settings.py
"""
Single source of truth for environment-driven configuration.

IMPORTANT: this module calls load_dotenv() at import time, and every other
module reads its config THROUGH this module (`from config import settings`,
then `settings.SMTP_USER`) rather than snapshotting values into their own
module-level constants.

Why that matters: services/email_service.py used to do
    SMTP_USER = os.environ.get("SMTP_USER")
at import time. That only worked because main.py happened to import
database.db (which calls load_dotenv()) before importing the routers. Change
the import order and SMTP_USER becomes None with no error — emails then fail
silently forever. Reading through the module attribute removes that trap.
"""
import os

from dotenv import load_dotenv

load_dotenv()

# ── URLs ──────────────────────────────────────────────────────────
# Public URL of THIS backend. Used to build certificate download links
# that are emailed to citizens, so it MUST be reachable from outside —
# "localhost" only works in local development.
BACKEND_BASE_URL = os.getenv("BACKEND_BASE_URL", "http://localhost:8000")

# Public URL of the React frontend. Used for the QR code's /verify page.
# Deliberately separate from BACKEND_BASE_URL — different servers.
FRONTEND_BASE_URL = os.getenv("FRONTEND_BASE_URL", "http://localhost:5173")

# ── Database ──────────────────────────────────────────────────────
DATABASE_URL = os.getenv("DATABASE_URL")

# ── SMTP / email ──────────────────────────────────────────────────
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT") or 587)
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
FROM_EMAIL = os.getenv("FROM_EMAIL") or SMTP_USER


def smtp_is_configured() -> bool:
    """True when the app has everything it needs to actually send mail."""
    return bool(SMTP_USER and SMTP_PASSWORD)