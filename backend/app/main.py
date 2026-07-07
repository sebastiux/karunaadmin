"""Karuna Admin API — FastAPI application entrypoint."""
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

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


# --------------------------------------------------------------------------- #
# Serve the built React frontend from the same service (single-container deploy)
# --------------------------------------------------------------------------- #
# The Docker build copies frontend/dist -> app/static. When present, the SPA is
# served at "/" and unknown paths fall back to index.html for client-side
# routing. API routes (registered above) and /docs still take precedence. When
# absent (pure API dev), we expose a small JSON root instead.
_STATIC_DIR = Path(__file__).parent / "static"

if _STATIC_DIR.is_dir():
    _assets = _STATIC_DIR / "assets"
    if _assets.is_dir():
        app.mount("/assets", StaticFiles(directory=_assets), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        candidate = (_STATIC_DIR / full_path).resolve()
        # Serve real files (favicon, etc.); otherwise hand off to the SPA.
        if (
            full_path
            and candidate.is_file()
            and str(candidate).startswith(str(_STATIC_DIR.resolve()))
        ):
            return FileResponse(candidate)
        return FileResponse(_STATIC_DIR / "index.html")

else:

    @app.get("/", tags=["health"])
    def root():
        return {"service": "karuna-admin-api", "docs": "/docs"}
