import datetime as dt
from enum import Enum

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import relationship

from app.database import Base


class PlanName(str, Enum):
    FREE = "free"
    PRO = "pro"


class TenantStatus(str, Enum):
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELED = "canceled"


class UsageType(str, Enum):
    API_CALL = "api_call"
    AI_TOKEN = "ai_token"


class Plan(Base):
    __tablename__ = "plans"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    api_calls_limit = Column(Integer, nullable=False)
    ai_tokens_limit = Column(Integer, nullable=False)
    price_cents = Column(Integer, nullable=False, default=0)
    stripe_price_id = Column(String, nullable=True)


class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, nullable=False)
    plan_id = Column(Integer, ForeignKey("plans.id"), nullable=False)
    stripe_customer_id = Column(String, nullable=True)
    status = Column(String, nullable=False, default=TenantStatus.ACTIVE)

    plan = relationship("Plan")


class UsageEvent(Base):
    __tablename__ = "usage_events"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    type = Column(String, nullable=False)
    quantity = Column(Integer, nullable=False)
    input_tokens = Column(Integer, nullable=True, default=0)
    cached_input_tokens = Column(Integer, nullable=True, default=0)
    output_tokens = Column(Integer, nullable=True, default=0)
    reasoning_tokens = Column(Integer, nullable=True, default=0)
    idempotency_key = Column(String, nullable=False)
    created_at = Column(DateTime, default=dt.datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_usage_event_idempotency_key"),
        Index("idx_usage_events_tenant_type_created", "tenant_id", "type", "created_at"),
    )


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    stripe_subscription_id = Column(String, unique=True, nullable=False)
    status = Column(String, nullable=False)
    current_period_start = Column(DateTime, nullable=True)
    current_period_end = Column(DateTime, nullable=True)


class ProcessedStripeEvent(Base):
    __tablename__ = "processed_stripe_events"

    id = Column(Integer, primary_key=True, index=True)
    stripe_event_id = Column(String, unique=True, nullable=False)
    type = Column(String, nullable=False)
    processed_at = Column(DateTime, default=dt.datetime.utcnow, nullable=False)
