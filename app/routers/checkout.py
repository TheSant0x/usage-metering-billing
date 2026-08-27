from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import CheckoutCreate, CheckoutOut
from app.services.stripe_client import create_checkout_session

router = APIRouter(tags=["billing"])


@router.post("/checkout", response_model=CheckoutOut)
def checkout(payload: CheckoutCreate, db: Session = Depends(get_db)):
    url = create_checkout_session(db, payload.tenant_id)
    return CheckoutOut(checkout_url=url)


@router.get("/checkout/success")
def checkout_success(session_id: str):
    return {"session_id": session_id, "status": "checkout_completed"}


@router.get("/checkout/cancel")
def checkout_cancel():
    return {"status": "checkout_cancelled"}
