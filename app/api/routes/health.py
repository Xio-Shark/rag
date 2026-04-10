from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_session_dep, get_settings_dep
from app.core.config import Settings
from app.db.models import Chunk, Document
from app.db.session import get_database_compatibility_status, ping_database
from app.schemas.health import HealthResponse
from app.services.embeddings import get_embedding_backend_name
from app.services.generator import get_generator_backend_name

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def get_health(
    session: Session = Depends(get_session_dep),
    settings: Settings = Depends(get_settings_dep),
) -> HealthResponse:
    document_count = len(list(session.scalars(select(Document))))
    chunk_count = len(list(session.scalars(select(Chunk))))
    compatibility = get_database_compatibility_status(session.get_bind())
    return HealthResponse(
        app_name=settings.app_name,
        database_ok=ping_database(),
        database_backend=compatibility.database_backend,
        generator_backend=get_generator_backend_name(settings),
        embedding_backend=get_embedding_backend_name(settings),
        embedding_storage=compatibility.embedding_storage,
        feature_flags=settings.feature_flags,
        index_strategy="exact",
        document_count=document_count,
        chunk_count=chunk_count,
    )
