import datetime as dt
from typing import Optional
from pydantic import BaseModel, EmailStr, Field


class TenantCreate(BaseModel):
    name: str
    email: EmailStr


class TenantOut(BaseModel):
    id: int
    name: str
    email: str
    plan_id: int
    plan_name: str
    stripe_customer_id: Optional[str]
    status: str

    class Config:
        from_attributes = True


class GenerateRequest(BaseModel):
    tenant_id: int
    api_calls: int = 1
    input_tokens: int = 0
    cached_input_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0


class GenerateResponse(BaseModel):
    tenant_id: int
    accepted: bool
    message: str
    usage_event_id: Optional[int] = None


class UsageItem(BaseModel):
    type: str
    used: int
    limit: int
    cost_cents: int


class UsageOut(BaseModel):
    tenant_id: int
    plan_name: str
    period_start: dt.datetime
    period_end: dt.datetime
    items: list[UsageItem]
    total_cost_cents: int


class CheckoutCreate(BaseModel):
    tenant_id: int


class CheckoutOut(BaseModel):
    checkout_url: str


class StripeWebhookOut(BaseModel):
    status: str
