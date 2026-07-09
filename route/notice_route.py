from fastapi import HTTPException,APIRouter, Depends
from fastapi.responses import JSONResponse
from database.db import get_db
from model.notice_model import NoticeModel as Notice
from model.ward_model import WardModel
from schema.notice_schema import NoticeCreate, NoticeResponse
from auth.current_user import require_permission
from uuid import UUID
router = APIRouter(
    prefix="/v1/notice",
    tags=["notice"]
)
@router.post("/create")
def create_notice(notice: NoticeCreate, db=Depends(get_db), current_user=Depends(require_permission("read_user"))):
    try:
        print("Current User:", current_user)
        ward = db.query(WardModel).filter(WardModel.ward_id == current_user.user_ward_id).first()
        if not ward:
            raise HTTPException(status_code=404, detail="Ward not found")

        new_notice = Notice(
            notice_ward_id=ward.ward_id,
            notice_title=notice.notice_title,
            notice_description=notice.notice_description,
            notice_type=notice.notice_type,
            notice_status=notice.status,
    
        )
        db.add(new_notice)
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
        raise HTTPException(status_code=500, detail=str(e))
    
@router.get("/{ward_id}/all")
def get_all_notices(ward_id: UUID, db=Depends(get_db), current_user=Depends(require_permission("view_notices"))):
    try:
        notices = db.query(Notice).filter(Notice.notice_ward_id == ward_id).all()
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