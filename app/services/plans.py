from sqlalchemy.orm import Session

from app.models import Plan


def seed_plans(db: Session) -> None:
    """Seed default Free and Pro plans if they do not exist."""
    existing = {p.name for p in db.query(Plan.name).all()}
    plans = [
        Plan(
            name="free",
            api_calls_limit=1000,
            ai_tokens_limit=100_000,
            price_cents=0,
            stripe_price_id=None,
        ),
        Plan(
            name="pro",
            api_calls_limit=10_000,
            ai_tokens_limit=1_000_000,
            price_cents=999,
            stripe_price_id=None,
        ),
    ]
    for plan in plans:
        if plan.name not in existing:
            db.add(plan)
    db.commit()


def get_plan_by_name(db: Session, name: str) -> Plan | None:
    return db.query(Plan).filter(Plan.name == name).first()
