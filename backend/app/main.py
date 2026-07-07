"""Karuna Admin API — FastAPI application entrypoint."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import auth, deliverables, kanban, monitoring, projects
from app.seed import init_db
from app.services.grok import grok

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("karunaadmin")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Karuna Admin API")
    try:
        init_db()
    except Exception as exc:  # don't crash the whole app if DB is briefly down
        logger.error("DB init failed at startup: %s", exc)
    logger.info(
        "Grok AI: %s", "ENABLED" if grok.enabled else "MOCK MODE (no GROK_API_KEY)"
    )
    yield


app = FastAPI(
    title="Karuna Admin API",
    description="Project administration platform: code review, deliverables + AI, "
    "and client monitoring.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(deliverables.router)
app.include_router(kanban.router)
app.include_router(monitoring.router)


@app.get("/api/health", tags=["health"])
def health():
    return {"status": "ok", "grok": "enabled" if grok.enabled else "mock"}


@app.get("/", tags=["health"])
def root():
    return {"service": "karuna-admin-api", "docs": "/docs"}
