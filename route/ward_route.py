from fastapi import HTTPException, APIRouter, Depends, UploadFile, File
from fastapi.responses import JSONResponse
from database.db import get_db
from model.ward_model import WardModel
from schema.ward_schema import WardResponse
from auth.current_user import require_permission
import os
import shutil
import uuid as uuid_lib
from fastapi.responses import JSONResponse
from uuid import UUID

router = APIRouter(
    prefix="/v1/ward",
    tags=["ward"]
)


@router.get("/all")
def get_all_wards(
    db=Depends(get_db),
    
    
):
    try:
        wards = (
            db.query(WardModel)
            .order_by(
                WardModel.ward_province,
                WardModel.ward_district,
                WardModel.ward_municipality,
                WardModel.ward_no,
            )
            .all()
        )

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "status_code": 200,
                "message": "Wards fetched successfully",
                "total": len(wards),
                "data": [
                    WardResponse.model_validate(ward).model_dump(mode="json")
                    for ward in wards
                ],
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    

ALLOWED_TYPES = {"image/png", "image/jpeg", "image/jpg", "image/webp"}
UPLOAD_DIR = "static/wards"

def _save_image(ward_id: UUID, file: UploadFile, suffix: str) -> str:
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail="Only PNG/JPEG/WEBP images allowed")

    ext = os.path.splitext(file.filename)[1] or ".png"
    ward_dir = os.path.join(UPLOAD_DIR, str(ward_id))
    os.makedirs(ward_dir, exist_ok=True)

    filename = f"{suffix}_{uuid_lib.uuid4().hex[:8]}{ext}"
    filepath = os.path.join(ward_dir, filename)

    with open(filepath, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # path relative to /static mount, e.g. "wards/<ward_id>/logo_ab12cd34.png"
    return f"wards/{ward_id}/{filename}"


@router.post("/{ward_id}/upload-images")
def upload_ward_images(
    ward_id: UUID,
    logo: UploadFile = File(None),
    chairperson_signature: UploadFile = File(None),
    chairperson_stamp: UploadFile = File(None),
    db=Depends(get_db),
    current_user=Depends(require_permission("create_user")),  # adjust to your actual permission
):
    ward = db.query(WardModel).filter(WardModel.ward_id == ward_id).first()
    if not ward:
        raise HTTPException(status_code=404, detail="Ward not found")

    try:
        if logo:
            ward.ward_logo_path = _save_image(ward_id, logo, "logo")
        if chairperson_signature:
            ward.chairperson_signature_path = _save_image(ward_id, chairperson_signature, "signature")
        if chairperson_stamp:
            ward.chairperson_stamp_path = _save_image(ward_id, chairperson_stamp, "stamp")

        db.commit()
        db.refresh(ward)

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "status_code": 200,
                "message": "Ward images uploaded successfully",
                "data": {
                    "ward_logo_path": ward.ward_logo_path,
                    "chairperson_signature_path": ward.chairperson_signature_path,
                    "chairperson_stamp_path": ward.chairperson_stamp_path,
                },
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))