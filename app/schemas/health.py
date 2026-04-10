from __future__ import annotations

from pydantic import BaseModel


class HealthResponse(BaseModel):
    app_name: str
    database_ok: bool
    database_backend: str
    generator_backend: str
    embedding_backend: str
    embedding_storage: str
    feature_flags: dict[str, bool]
    index_strategy: str
    document_count: int
    chunk_count: int
