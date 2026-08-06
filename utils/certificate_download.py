# utils/certificate_download.py
import os
import requests
from fastapi import HTTPException
from fastapi.responses import Response


def stream_certificate_pdf(pdf_url: str, filename: str) -> Response:
    """
    Fetches a certificate/receipt PDF from its stored location and
    returns it as an inline PDF response — same "renders in an <iframe>
    instead of forcing a download" behavior the old FileResponse(local
    path) calls had, just sourced from Cloudinary now instead of the
    static/ mount.

    pdf_url is normally a full Cloudinary secure_url (what
    render_certificate_pdf / render_receipt_pdf now return). For
    certificates issued before the Cloudinary switch, it may still be a
    legacy path relative to the static/ mount — handled here too, so old
    download links keep working without a data migration.
    """
    if not pdf_url:
        raise HTTPException(status_code=404, detail="Certificate file missing on server")

    try:
        if pdf_url.startswith("http://") or pdf_url.startswith("https://"):
            resp = requests.get(pdf_url, timeout=15)
            resp.raise_for_status()
            content = resp.content
        else:
            abs_path = os.path.join("static", pdf_url)
            if not os.path.exists(abs_path):
                raise HTTPException(status_code=404, detail="Certificate file missing on server")
            with open(abs_path, "rb") as f:
                content = f.read()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Could not retrieve certificate file: {e}")

    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}.pdf"'},
    )