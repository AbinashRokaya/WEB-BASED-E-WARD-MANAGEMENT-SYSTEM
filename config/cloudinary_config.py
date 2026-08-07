# config/cloudinary_config.py
"""
Central Cloudinary configuration.

Import this module ONCE, early (e.g. at the top of main.py, or at the top
of every module that calls cloudinary.uploader.upload) so cloudinary.config()
runs before any upload call. Calling cloudinary.config() multiple times is
harmless/idempotent, so importing it from several files is fine.

Credentials come ONLY from environment variables — never hardcode them.
Put them in a .env file that is in .gitignore, e.g.:

    CLOUDINARY_CLOUD_NAME=dzni43etp
    CLOUDINARY_API_KEY=your_key
    CLOUDINARY_API_SECRET=your_secret

and load it (e.g. via python-dotenv's load_dotenv()) before this module
is imported.
"""
import os
import cloudinary

_missing = [
    var for var in ("CLOUDINARY_CLOUD_NAME", "CLOUDINARY_API_KEY", "CLOUDINARY_API_SECRET")
    if not os.environ.get(var)
]
if _missing:
    raise RuntimeError(
        f"Missing required Cloudinary env vars: {', '.join(_missing)}. "
        "Set them in your .env file (see cloudinary_config.py docstring)."
    )

cloudinary.config(
    cloud_name=os.environ["CLOUDINARY_CLOUD_NAME"],
    api_key=os.environ["CLOUDINARY_API_KEY"],
    api_secret=os.environ["CLOUDINARY_API_SECRET"],
    secure=True,
)