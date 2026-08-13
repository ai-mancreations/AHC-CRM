from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.db import init_db

from app.routers import (
    auth,
    branches,
    leads,
    calls_followups,
    appointments,
    customers,
    services,
    inventory,
    invoices,
    expenses,
    marketing,
    notifications,
    reports,
    settings_generic,
    public_intake,
    dashboard,
    ai_assistant,
    audit_users,
)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

routers = [
    auth.router,
    branches.router,
    leads.router,
    calls_followups.router,
    appointments.router,
    customers.router,
    services.router,
    inventory.router,
    invoices.router,
    expenses.router,
    marketing.router,
    notifications.router,
    reports.router,
    settings_generic.router,
    public_intake.router,
    dashboard.router,
    ai_assistant.router,
    audit_users.audit_router,
    audit_users.users_router,
]

for r in routers:
    app.include_router(r)


@app.get("/api/health")
async def health():
    return {"status": "ok", "app": settings.APP_NAME}
