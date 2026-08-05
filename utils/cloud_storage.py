import os
import cloudinary
import cloudinary.uploader
from dotenv import load_dotenv

load_dotenv()

cloudinary.config(
    cloud_name=os.getenv("CLOUD_NAME"),
    api_key=os.getenv("API_KEY"),
    api_secret=os.getenv("API_SECRET"),
    secure=True,
)

ALLOWED_IMAGE_TYPES = {"image/png", "image/jpeg", "image/jpg", "image/webp"}
ALLOWED_DOC_TYPES = ALLOWED_IMAGE_TYPES | {"application/pdf"}

# Word docs aren't renderable image-type assets on Cloudinary — they need
# resource_type="raw". Notices are the only place .doc/.docx are accepted.
_RAW_TYPES = {
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
ALLOWED_NOTICE_TYPES = ALLOWED_DOC_TYPES | _RAW_TYPES


def upload_document(file_bytes: bytes, folder: str, public_id: str, content_type: str) -> str:
    """Uploads in-memory bytes to Cloudinary and returns the secure_url.
    Images/PDFs go through as resource_type='image' (Cloudinary treats PDFs
    as a special image asset); Word docs go through as resource_type='raw'."""
    upload_kwargs = {
        "public_id": public_id,
        "folder": folder,
        "overwrite": True,
    }
    if content_type in _RAW_TYPES:
        upload_kwargs["resource_type"] = "raw"
    else:
        upload_kwargs["resource_type"] = "image"
        if content_type == "application/pdf":
            upload_kwargs["format"] = "pdf"

    result = cloudinary.uploader.upload(file_bytes, **upload_kwargs)
    return result.get("secure_url")


def upload_local_file(local_path: str, folder: str, public_id: str, resource_type: str = "image") -> str:
    """Uploads a file already on disk (e.g. a Playwright-rendered PDF or a
    qrcode PNG written to a temp file) to Cloudinary and returns the secure_url."""
    result = cloudinary.uploader.upload(
        local_path,
        public_id=public_id,
        folder=folder,
        resource_type=resource_type,
        overwrite=True,
    )
    return result.get("secure_url")