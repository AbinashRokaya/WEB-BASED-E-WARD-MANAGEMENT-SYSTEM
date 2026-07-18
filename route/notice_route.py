from fastapi import HTTPException, APIRouter, Depends, UploadFile, File, Form
from fastapi.responses import JSONResponse
from typing import Optional
from datetime import date, datetime, time
from database.db import get_db
from model.notice_model import NoticeModel as Notice
from model.ward_model import WardModel
from schema.notice_schema import NoticeCreate, NoticeResponse, NoticeType, NoticeStatus
from auth.current_user import require_permission
from uuid import UUID
import os
import shutil
import uuid as uuid_lib

router = APIRouter(
    prefix="/v1/notice",
    tags=["notice"]
)

ALLOWED_TYPES = {
    "image/png", "image/jpeg", "image/jpg", "image/webp",
    "application/pdf",
    "application/msword",  # .doc
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # .docx
}
UPLOAD_DIR = "static/notices"


def save_notice_attachment(notice_id, file: UploadFile) -> tuple[str, str]:
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=400,
            detail="Only PNG, JPEG, WEBP, PDF, DOC, or DOCX files are allowed"
        )

    ext = os.path.splitext(file.filename)[1] or ""
    notice_dir = os.path.join(UPLOAD_DIR, str(notice_id))
    os.makedirs(notice_dir, exist_ok=True)

    filename = f"file_{uuid_lib.uuid4().hex[:8]}{ext}"
    filepath = os.path.join(notice_dir, filename)

    with open(filepath, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    return f"notices/{notice_id}/{filename}", file.content_type  # (relative path, mime type)


@router.post("/create")
def create_notice(
    notice_title: str = Form(...),
    notice_description: str = Form(...),
    notice_type: NoticeType = Form(...),
    status: NoticeStatus = Form(NoticeStatus.DRAFT),
    attachment: UploadFile = File(None),
    db=Depends(get_db),
    current_user=Depends(require_permission("read_user")),
):
    try:
        ward = db.query(WardModel).filter(WardModel.ward_id == current_user.user_ward_id).first()
        if not ward:
            raise HTTPException(status_code=404, detail="Ward not found")

        new_notice = Notice(
            notice_ward_id=ward.ward_id,
            notice_title=notice_title,
            notice_description=notice_description,
            notice_type=notice_type,
            notice_status=status,
        )
        db.add(new_notice)
        db.flush()

        if attachment:
            path, mime_type = save_notice_attachment(new_notice.notice_id, attachment)
            new_notice.notice_attachment_path = path
            new_notice.notice_attachment_type = mime_type

        db.commit()
        db.refresh(new_notice)

        return JSONResponse(
            status_code=201,
            content={
                "success": True,
                "status_code": 201,
                "message": "Notice created successfully",
                "data": NoticeResponse.model_validate(new_notice).model_dump(mode="json")
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    

@router.get("/{ward_id}/all")
def get_all_notices(
    ward_id: UUID,
    notice_type: Optional[NoticeType] = None,
    notice_status: Optional[NoticeStatus] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    db=Depends(get_db),
    current_user=Depends(require_permission("read_user")),
):
    try:
        query = db.query(Notice).filter(Notice.notice_ward_id == ward_id)

        if notice_type:
            query = query.filter(Notice.notice_type == notice_type)
        if notice_status:
            query = query.filter(Notice.notice_status == notice_status)
        if date_from:
            query = query.filter(Notice.created_at >= datetime.combine(date_from, time.min))
        if date_to:
            query = query.filter(Notice.created_at <= datetime.combine(date_to, time.max))

        notices = query.order_by(Notice.created_at.desc()).all()

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "status_code": 200,
                "data": [NoticeResponse.model_validate(notice).model_dump(mode="json") for notice in notices]
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))