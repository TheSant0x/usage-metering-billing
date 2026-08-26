import uuid
from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import UsageType
from app.schemas import GenerateRequest, GenerateResponse
from app.services.meter import record_usage

router = APIRouter(tags=["billing"])


@router.post("/generate", response_model=GenerateResponse)
def generate(
    payload: GenerateRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
):
    if not idempotency_key:
        idempotency_key = str(uuid.uuid4())

    # API call usage
    api_event = record_usage(
        db=db,
        tenant_id=payload.tenant_id,
        usage_type=UsageType.API_CALL,
        quantity=payload.api_calls,
        idempotency_key=f"{idempotency_key}:api",
    )

    # AI token usage
    total_tokens = (
        payload.input_tokens
        + payload.cached_input_tokens
        + payload.output_tokens
        + payload.reasoning_tokens
    )
    token_event = None
    if total_tokens > 0:
        token_event = record_usage(
            db=db,
            tenant_id=payload.tenant_id,
            usage_type=UsageType.AI_TOKEN,
            quantity=total_tokens,
            idempotency_key=f"{idempotency_key}:tokens",
            token_breakdown={
                "input": payload.input_tokens,
                "cached_input": payload.cached_input_tokens,
                "output": payload.output_tokens,
                "reasoning": payload.reasoning_tokens,
            },
        )

    return GenerateResponse(
        tenant_id=payload.tenant_id,
        accepted=True,
        message="Usage recorded successfully",
        usage_event_id=token_event.id if token_event else api_event.id,
    )
