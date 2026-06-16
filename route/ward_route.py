import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from database.db import get_db
from schema.ward_schema import WardRequest, WardResponse
from model.ward_model import WardModel

router = APIRouter(prefix="/ward", tags=["Ward"])


@router.post("/", response_model=WardResponse, status_code=status.HTTP_201_CREATED)
def create_ward(payload: WardRequest, db: Session = Depends(get_db)):
    existing = db.query(WardModel).filter(WardModel.ward_email == payload.ward_email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Ward email already registered")

    ward = WardModel(**payload.dict())
    db.add(ward)
    db.commit()
    db.refresh(ward)
    return ward


@router.get("/", response_model=List[WardResponse])
def list_wards(db: Session = Depends(get_db)):
    return db.query(WardModel).all()


@router.get("/{ward_id}", response_model=WardResponse)
def get_ward(ward_id: uuid.UUID, db: Session = Depends(get_db)):
    ward = db.query(WardModel).filter(WardModel.ward_id == ward_id).first()
    if not ward:
        raise HTTPException(status_code=404, detail="Ward not found")
    return ward


@router.put("/{ward_id}", response_model=WardResponse)
def update_ward(ward_id: uuid.UUID, payload: WardRequest, db: Session = Depends(get_db)):
    ward = db.query(WardModel).filter(WardModel.ward_id == ward_id).first()
    if not ward:
        raise HTTPException(status_code=404, detail="Ward not found")

    for field, value in payload.dict().items():
        setattr(ward, field, value)

    db.commit()
    db.refresh(ward)
    return ward


@router.delete("/{ward_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_ward(ward_id: uuid.UUID, db: Session = Depends(get_db)):
    ward = db.query(WardModel).filter(WardModel.ward_id == ward_id).first()
    if not ward:
        raise HTTPException(status_code=404, detail="Ward not found")
    db.delete(ward)
    db.commit()