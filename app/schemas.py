import datetime as dt
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, field_validator


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

    model_config = {"from_attributes": True}


class GenerateRequest(BaseModel):
    tenant_id: int = Field(..., ge=1)
    api_calls: int = Field(default=1, ge=0)
    input_tokens: int = Field(default=0, ge=0)
    cached_input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    reasoning_tokens: int = Field(default=0, ge=0)

    @field_validator("tenant_id")
    @classmethod
    def tenant_id_must_be_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("tenant_id must be positive")
        return v


class GenerateResponse(BaseModel):
    tenant_id: int
    accepted: bool
    message: str
    usage_event_id: Optional[int] = None


class UsageItem(BaseModel):
    type: str
    used: int
    limit: int
    cost_millicents: int
    cost_cents: int


class UsageOut(BaseModel):
    tenant_id: int
    plan_name: str
    period_start: dt.datetime
    period_end: dt.datetime
    items: list[UsageItem]
    total_cost_millicents: int
    total_cost_cents: int


class CheckoutCreate(BaseModel):
    tenant_id: int


class CheckoutOut(BaseModel):
    checkout_url: str


class StripeWebhookOut(BaseModel):
    status: str
