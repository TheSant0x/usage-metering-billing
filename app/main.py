from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.database import engine, Base
from app.jobs.scheduler import start_scheduler, stop_scheduler
from app.routers import tenants, generate, usage, checkout, webhooks

Base.metadata.create_all(bind=engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(
    title="FlyRank Usage Metering & Billing Engine",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(tenants.router)
app.include_router(generate.router)
app.include_router(usage.router)
app.include_router(checkout.router)
app.include_router(webhooks.router)


@app.get("/health")
def health():
    return {"status": "ok"}
