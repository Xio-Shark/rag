from __future__ import annotations

import json
import logging
from pathlib import Path

from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parents[1]


def _observability_events(caplog) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    for record in caplog.records:
        try:
            payload = json.loads(record.getMessage())
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and payload.get("event"):
            events.append(payload)
    return events


def test_health_request_adds_request_id_and_request_log(prepared_environment, caplog) -> None:
    from app.db.session import init_database
    from app.main import app

    init_database()
    caplog.set_level(logging.INFO, logger="rag.observability")

    with TestClient(app) as client:
        response = client.get("/v1/health")

    assert response.status_code == 200
    request_id = response.headers["X-Request-ID"]
    assert request_id

    request_event = next(
        event
        for event in _observability_events(caplog)
        if event["event"] == "http.request.completed" and event["path"] == "/v1/health"
    )
    assert request_event["request_id"] == request_id
    assert request_event["method"] == "GET"
    assert request_event["status_code"] == 200
    assert float(request_event["duration_ms"]) >= 0


def test_health_request_reuses_incoming_request_id(prepared_environment, caplog) -> None:
    from app.db.session import init_database
    from app.main import app

    init_database()
    caplog.set_level(logging.INFO, logger="rag.observability")

    with TestClient(app) as client:
        response = client.get("/v1/health", headers={"X-Request-ID": "req-observe-001"})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "req-observe-001"

    request_event = next(
        event
        for event in _observability_events(caplog)
        if event["event"] == "http.request.completed" and event["path"] == "/v1/health"
    )
    assert request_event["request_id"] == "req-observe-001"


def test_document_import_emits_completion_log(prepared_environment, caplog) -> None:
    from app.db.session import init_database
    from app.main import app

    init_database()
    caplog.set_level(logging.INFO, logger="rag.observability")

    with TestClient(app) as client:
        response = client.post("/v1/documents/import", json={})
        payload = response.json()

    assert response.status_code == 200

    import_event = next(
        event
        for event in _observability_events(caplog)
        if event["event"] == "documents.import.completed"
    )
    assert import_event["request_id"] == response.headers["X-Request-ID"]
    assert import_event["imported_count"] == payload["imported_count"]
    assert import_event["skipped_count"] == payload["skipped_count"]
    assert import_event["chunk_count"] == payload["chunk_count"]


def test_qa_ask_emits_completion_log_with_audit_id(prepared_environment, caplog) -> None:
    from app.db.session import init_database
    from app.main import app

    init_database()
    caplog.set_level(logging.INFO, logger="rag.observability")

    with TestClient(app) as client:
        import_response = client.post("/v1/documents/import", json={})
        assert import_response.status_code == 200
        caplog.clear()
        response = client.post(
            "/v1/qa/ask",
            json={"query": "系统支持哪些核心能力？", "top_k": 3},
        )
        payload = response.json()

    assert response.status_code == 200

    ask_event = next(
        event for event in _observability_events(caplog) if event["event"] == "qa.ask.completed"
    )
    assert ask_event["request_id"] == response.headers["X-Request-ID"]
    assert ask_event["audit_id"] == payload["audit_id"]
    assert ask_event["citation_count"] == len(payload["citations"])
    assert ask_event["refused"] is False


def test_eval_run_emits_completion_log_with_eval_run_id(prepared_environment, caplog) -> None:
    from app.db.session import init_database
    from app.main import app

    init_database()
    caplog.set_level(logging.INFO, logger="rag.observability")

    with TestClient(app) as client:
        import_response = client.post("/v1/documents/import", json={})
        assert import_response.status_code == 200
        caplog.clear()
        response = client.post(
            "/v1/evals/run",
            json={"dataset_name": "baseline_v1", "snapshot_name": "default"},
        )
        payload = response.json()

    assert response.status_code == 200

    eval_event = next(
        event for event in _observability_events(caplog) if event["event"] == "eval.run.completed"
    )
    assert eval_event["request_id"] == response.headers["X-Request-ID"]
    assert eval_event["eval_run_id"] == payload["eval_run_id"]
    assert eval_event["dataset_name"] == "baseline_v1"
    assert eval_event["snapshot_name"] == "default"
    assert eval_event["case_count"] == payload["case_count"]


def test_observability_docs_reference_request_id_and_log_level() -> None:
    readme_text = (ROOT_DIR / "README.md").read_text(encoding="utf-8")
    architecture_text = (ROOT_DIR / "ARCHITECTURE.md").read_text(encoding="utf-8")
    runbook_text = (ROOT_DIR / "RUNBOOK.md").read_text(encoding="utf-8")
    env_example_text = (ROOT_DIR / ".env.example").read_text(encoding="utf-8")

    assert "X-Request-ID" in readme_text
    assert "X-Request-ID" in architecture_text
    assert "X-Request-ID" in runbook_text
    assert "APP_LOG_LEVEL" in readme_text
    assert "APP_LOG_LEVEL" in runbook_text
    assert "APP_LOG_LEVEL=INFO" in env_example_text
