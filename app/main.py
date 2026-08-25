from fastapi import FastAPI

from app.database import engine, Base
from app.routers import tenants

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="FlyRank Usage Metering & Billing Engine",
    version="1.0.0",
)

app.include_router(tenants.router)


@app.get("/health")
def health():
    return {"status": "ok"}
