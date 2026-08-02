"""
Khalti ePayment integration for tax payments.

Unlike the standalone Khalti demo (which takes name/email/phone from a
form the user types), every call here builds customer_info from the
LOGGED-IN CITIZEN'S OWN ACCOUNT (current_user) — never from client input.
This matters for tax specifically: a payment receipt has to actually
belong to the person paying, and there's no legitimate case for typing
in someone else's details when paying your own tax bill.
"""
import os
import httpx
from dotenv import load_dotenv

# Pass an explicit path so this loads regardless of the working directory
# uvicorn happens to be launched from. Adjust if your .env lives
# somewhere else relative to this file.
load_dotenv()

KHALTI_SECRET_KEY = os.getenv("KHALTI_SECRET_KEY")
KHALTI_BASE_URL = os.getenv("KHALTI_BASE_URL", "https://dev.khalti.com/api/v2")

# Backend's own public base — where Khalti redirects the browser back to
# after payment (this app's /v1/tax/payments/khalti/verify), NOT the
# frontend. Separate from FRONTEND_BASE_URL below, same distinction your
# birth-certificate module already draws between BACKEND_BASE_URL and
# VERIFY_BASE_URL.
APP_BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:8000")

# Where the citizen actually ends up after verify finishes — your React
# app's tax page. Adjust to wherever MyTaxDashboard is actually reachable
# in your routing.
FRONTEND_BASE_URL = os.getenv("FRONTEND_BASE_URL", "http://localhost:5173")

HEADERS = {
    "Authorization": f"Key {KHALTI_SECRET_KEY}",
    "Content-Type": "application/json",
}


def _require_secret_key():
    # Fails loudly and specifically instead of silently sending
    # "Authorization: Key None" and letting Khalti's rejection surface
    # as a confusing downstream JSON-parse crash.
    if not KHALTI_SECRET_KEY:
        raise ValueError(
            "KHALTI_SECRET_KEY is not set — check that your .env file is "
            "in the directory uvicorn is launched from, or that the "
            "environment variable is exported before starting the server."
        )


async def initiate_khalti_payment(
    amount_rs: float,
    purchase_order_id: str,
    purchase_order_name: str,
    customer_name: str,
    customer_email: str,
    customer_phone: str,
) -> dict:
    """Returns Khalti's response dict, which contains `pidx` and
    `payment_url` on success. Raises ValueError on any failure, with a
    message safe to show the citizen."""
    _require_secret_key()

    payload = {
        "return_url": f"{APP_BASE_URL}/v1/tax/payments/khalti/verify",
        "website_url": APP_BASE_URL,
        "amount": int(round(amount_rs * 100)),  # Khalti wants paisa, not rupees
        "purchase_order_id": purchase_order_id,
        "purchase_order_name": purchase_order_name,
        "customer_info": {
            "name": customer_name,
            "email": customer_email,
            "phone": customer_phone,
        },
    }

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{KHALTI_BASE_URL}/epayment/initiate/", json=payload, headers=HEADERS
            )
    except httpx.RequestError as e:
        raise ValueError(f"Could not reach Khalti: {e}")

    # Parse defensively — an auth failure or a proxy error in front of
    # Khalti can return HTML/plain-text instead of JSON, and .json()
    # throwing here used to be uncaught, which is what turns into an
    # unhandled 500 on the FastAPI side instead of a clean error message.
    try:
        data = resp.json()
    except ValueError:
        raise ValueError(
            f"Khalti returned a non-JSON response (HTTP {resp.status_code}). "
            f"This usually means KHALTI_SECRET_KEY is missing or invalid. "
            f"Raw response: {resp.text[:300]}"
        )

    if resp.status_code != 200:
        detail = data.get("detail") if isinstance(data, dict) else None
        raise ValueError(detail or f"Khalti error (HTTP {resp.status_code}): {data}")

    return data


async def lookup_khalti_payment(pidx: str) -> dict:
    """Returns Khalti's lookup response dict — contains `status`
    (Completed/Pending/Expired/User canceled/Refunded) and, when
    Completed, `transaction_id` and `total_amount`."""
    _require_secret_key()

    payload = {"pidx": pidx}
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{KHALTI_BASE_URL}/epayment/lookup/", json=payload, headers=HEADERS
            )
    except httpx.RequestError as e:
        raise ValueError(f"Could not verify payment with Khalti: {e}")

    try:
        return resp.json()
    except ValueError:
        raise ValueError(
            f"Khalti returned a non-JSON response during lookup (HTTP {resp.status_code}). "
            f"Raw response: {resp.text[:300]}"
        )