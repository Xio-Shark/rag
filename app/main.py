from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes.documents import router as documents_router
from app.api.routes.evals import router as evals_router
from app.api.routes.health import router as health_router
from app.api.routes.qa import router as qa_router
from app.core.config import get_settings
from app.core.observability import configure_logging, observe_request
from app.db.session import init_database


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_database()
    yield

static_dir = Path(__file__).resolve().parent / "static"
settings = get_settings()

configure_logging(settings.app_log_level)

app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.middleware("http")(observe_request)
app.mount("/static", StaticFiles(directory=static_dir), name="static")
app.include_router(health_router, prefix="/v1")
app.include_router(documents_router, prefix="/v1")
app.include_router(qa_router, prefix="/v1")
app.include_router(evals_router, prefix="/v1")


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(static_dir / "index.html")
