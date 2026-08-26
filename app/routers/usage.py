from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import UsageOut
from app.services.meter import get_usage_summary

router = APIRouter(tags=["billing"])


@router.get("/usage/{tenant_id}", response_model=UsageOut)
def usage(tenant_id: int, db: Session = Depends(get_db)):
    summary = get_usage_summary(db, tenant_id)
    return UsageOut(**summary)
