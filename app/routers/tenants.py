from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Tenant, TenantStatus
from app.schemas import TenantCreate, TenantOut
from app.services.plans import seed_plans, get_plan_by_name

router = APIRouter(prefix="/tenants", tags=["tenants"])


@router.post("", response_model=TenantOut, status_code=status.HTTP_201_CREATED)
def create_tenant(payload: TenantCreate, db: Session = Depends(get_db)):
    seed_plans(db)
    free_plan = get_plan_by_name(db, "free")
    if not free_plan:
        raise HTTPException(status_code=500, detail="Default plans not seeded")

    tenant = Tenant(
        name=payload.name,
        email=payload.email,
        plan_id=free_plan.id,
        status=TenantStatus.ACTIVE,
    )
    db.add(tenant)
    db.commit()
    db.refresh(tenant)
    return _tenant_out(tenant)


@router.get("/{tenant_id}", response_model=TenantOut)
def read_tenant(tenant_id: int, db: Session = Depends(get_db)):
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return _tenant_out(tenant)


def _tenant_out(tenant: Tenant) -> TenantOut:
    return TenantOut(
        id=tenant.id,
        name=tenant.name,
        email=tenant.email,
        plan_id=tenant.plan_id,
        plan_name=tenant.plan.name,
        stripe_customer_id=tenant.stripe_customer_id,
        status=tenant.status,
    )
