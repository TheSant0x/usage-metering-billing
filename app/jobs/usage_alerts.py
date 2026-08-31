"""Simple background job that flags tenants approaching quota limits."""
import logging
from contextlib import contextmanager

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Tenant, UsageType
from app.services.meter import get_monthly_usage

logger = logging.getLogger(__name__)


@contextmanager
def _db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_usage_alerts(db: Session | None = None) -> None:
    """Log warnings for tenants above 80% of any quota."""
    if db is None:
        with _db_session() as db:
            return check_usage_alerts(db)

    tenants = db.query(Tenant).all()
    for tenant in tenants:
        plan = tenant.plan
        if not plan:
            continue

        api_used = get_monthly_usage(db, tenant.id, UsageType.API_CALL)
        if api_used >= plan.api_calls_limit * 0.8:
            logger.warning(
                "ALERT tenant=%s api_call usage=%s/%s (%.0f%%)",
                tenant.id,
                api_used,
                plan.api_calls_limit,
                100 * api_used / plan.api_calls_limit,
            )

        ai_used = get_monthly_usage(db, tenant.id, UsageType.AI_TOKEN)
        if ai_used >= plan.ai_tokens_limit * 0.8:
            logger.warning(
                "ALERT tenant=%s ai_token usage=%s/%s (%.0f%%)",
                tenant.id,
                ai_used,
                plan.ai_tokens_limit,
                100 * ai_used / plan.ai_tokens_limit,
            )
