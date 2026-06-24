from fastapi import HTTPException, APIRouter, Depends
from fastapi.responses import JSONResponse
from database.db import get_db
from model.ward_model import WardModel
from schema.ward_schema import WardResponse
from auth.current_user import require_permission

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