# main.py
import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# Imported FIRST so load_dotenv() runs before any module reads configuration.
from config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)

from route import (
    user_route,
    admin_route,
    ward_route,
    citizen_route,
    notice_route,
    birth_registration_route,
    certificate_router,
    deat_registration_route,
    migration_registration_route,
    recommendation_router,
    complaint_route,
    ward_secretary_route,
    ward_chairperson_route,
    data_validation_route,
    analytics_router,
    admin_analytics_router,
    tax_router,
)

app = FastAPI(
    title="e-Ward Management System API",
    description="ई-वडा व्यवस्थापन प्रणाली — backend API",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "https://e-ward-frontend.vercel.app",
    ],
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs("static/wards", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

# REMOVED: Base.metadata.create_all(bind=engine)
#
# Alembic owns this schema (see alembic/versions/). Running create_all() as
# well means SQLAlchemy silently creates tables Alembic has no migration for,
# and your migration history stops matching the real database — which is how
# "works on my machine, fails on deploy" starts. Apply schema changes with:
#     alembic upgrade head

# Registered as a list so adding a router is one line in one place, and so
# nothing can be imported-but-never-included (which silently 404s every route
# in that file).
ROUTERS = [
    user_route,
    admin_route,
    ward_route,
    citizen_route,
    notice_route,
    birth_registration_route,
    certificate_router,
    deat_registration_route,
    migration_registration_route,
    recommendation_router,
    complaint_route,
    ward_secretary_route,
    ward_chairperson_route,
    data_validation_route,
    analytics_router,
    admin_analytics_router,
    tax_router,
]

for module in ROUTERS:
    app.include_router(module.router)


@app.get("/", tags=["system"])
def read_root():
    return {"message": "e-Ward Management System API", "docs": "/docs"}


@app.get("/health", tags=["system"])
def health():
    """
    Answers "is this deploy actually able to send email?" in one request,
    instead of issuing a certificate and waiting to find out.
    """
    return {
        "status": "ok",
        "smtp_configured": settings.smtp_is_configured(),
        "backend_base_url": settings.BACKEND_BASE_URL,
    }


@app.on_event("startup")
def warn_on_missing_config():
    if not settings.smtp_is_configured():
        logger.warning(
            "SMTP_USER / SMTP_PASSWORD are not set — certificate emails will "
            "NOT be delivered. Set them in .env."
        )
    if "localhost" in settings.BACKEND_BASE_URL:
        logger.warning(
            "BACKEND_BASE_URL is %s — download links emailed to citizens will "
            "not work outside this machine. Set BACKEND_BASE_URL in .env.",
            settings.BACKEND_BASE_URL,
        )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)