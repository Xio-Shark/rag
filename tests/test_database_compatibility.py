from __future__ import annotations

from fastapi.testclient import TestClient


def _reset_runtime_caches() -> None:
    from app.core.config import get_settings
    from app.db.session import get_engine, get_session_factory

    get_settings.cache_clear()
    get_engine.cache_clear()
    get_session_factory.cache_clear()


def test_embedding_storage_backend_uses_json_for_sqlite() -> None:
    from app.db.types import get_embedding_storage_backend

    assert get_embedding_storage_backend("sqlite") == "json"


def test_embedding_storage_backend_uses_pgvector_when_available(
    monkeypatch,
) -> None:
    import app.db.types as db_types

    monkeypatch.setattr(db_types, "Vector", object())

    assert db_types.get_embedding_storage_backend("postgresql") == "pgvector"


def test_embedding_storage_backend_falls_back_to_json_without_pgvector(
    monkeypatch,
) -> None:
    import app.db.types as db_types

    monkeypatch.setattr(db_types, "Vector", None)

    assert db_types.get_embedding_storage_backend("postgresql") == "json"


def test_embedding_vector_exposes_pgvector_distance_operator() -> None:
    from app.db.models import Chunk

    expression = Chunk.embedding.cosine_distance([0.1])

    assert "<=>" in str(expression)


def test_health_api_exposes_database_compatibility(prepared_environment) -> None:
    from app.db.session import init_database
    from app.main import app

    init_database()

    with TestClient(app) as client:
        response = client.get("/v1/health")
        payload = response.json()

    assert response.status_code == 200
    assert payload["database_ok"] is True
    assert payload["database_backend"] == "sqlite"
    assert payload["embedding_backend"] == "hash"
    assert payload["embedding_storage"] == "json"
    assert payload["feature_flags"] == {
        "evals": True,
        "replay_experiments": True,
    }
    assert payload["document_count"] == 0
    assert payload["chunk_count"] == 0


def test_health_api_exposes_feature_flags(prepared_environment, monkeypatch) -> None:
    monkeypatch.setenv("FEATURE_EVALS_ENABLED", "false")
    monkeypatch.setenv("FEATURE_REPLAY_EXPERIMENTS_ENABLED", "false")
    _reset_runtime_caches()

    from app.db.session import init_database
    from app.main import app

    init_database()

    with TestClient(app) as client:
        response = client.get("/v1/health")
        payload = response.json()

    assert response.status_code == 200
    assert payload["feature_flags"] == {
        "evals": False,
        "replay_experiments": False,
    }
