from fastapi.testclient import TestClient


def _reset_runtime_caches() -> None:
    from app.core.config import get_settings
    from app.db.session import get_engine, get_session_factory

    get_settings.cache_clear()
    get_engine.cache_clear()
    get_session_factory.cache_clear()


def test_qa_api_returns_structured_answer(prepared_environment) -> None:
    from app.db.session import get_session_factory, init_database
    from app.main import app
    from app.services.ingestion import DocumentIngestionService

    init_database()
    session = get_session_factory()()
    try:
        DocumentIngestionService(session).import_directory(prepared_environment["docs_dir"])
        session.commit()
    finally:
        session.close()

    with TestClient(app) as client:
        response = client.post(
            "/v1/qa/ask",
            json={"query": "系统支持哪些核心能力？", "top_k": 3},
        )
        payload = response.json()
        runs_response = client.get("/v1/qa/runs?limit=10")
        audit_response = client.get(f"/v1/qa/runs/{payload['audit_id']}")
        audit_payload = audit_response.json()

    assert response.status_code == 200
    assert runs_response.status_code == 200
    assert audit_response.status_code == 200
    assert payload["audit_id"]
    assert payload["refusal_reason"] is None
    assert payload["citations"]
    assert payload["confidence"] > 0
    assert runs_response.json()["items"]
    assert audit_payload["query"] == "系统支持哪些核心能力？"
    assert audit_payload["retrieved_chunks"]
    assert audit_payload["failure_stage"] is None


def test_qa_api_refuses_without_evidence(prepared_environment) -> None:
    from app.db.session import get_session_factory, init_database
    from app.main import app
    from app.services.ingestion import DocumentIngestionService

    init_database()
    session = get_session_factory()()
    try:
        DocumentIngestionService(session).import_directory(prepared_environment["docs_dir"])
        session.commit()
    finally:
        session.close()

    with TestClient(app) as client:
        response = client.post(
            "/v1/qa/ask",
            json={"query": "系统支持图像生成吗？", "top_k": 3},
        )
        payload = response.json()

    assert response.status_code == 200
    assert payload["refusal_reason"] is not None


def test_eval_api_lists_snapshots_runs_and_compare(prepared_environment) -> None:
    from app.db.session import get_session_factory, init_database
    from app.main import app
    from app.services.evaluation import EvaluationService
    from app.services.ingestion import DocumentIngestionService

    init_database()
    session = get_session_factory()()
    try:
        DocumentIngestionService(session).import_directory(prepared_environment["docs_dir"])
        session.commit()
        service = EvaluationService(session)
        first = service.run(dataset_name="baseline_v1", snapshot_name="default")
        second = service.run(dataset_name="baseline_v1", snapshot_name="compact_context")
    finally:
        session.close()

    with TestClient(app) as client:
        snapshots_response = client.get("/v1/evals/snapshots")
        runs_response = client.get("/v1/evals/runs?limit=10")
        compare_response = client.get(
            f"/v1/evals/compare?base_eval_run_id={first.id}&target_eval_run_id={second.id}"
        )

    assert snapshots_response.status_code == 200
    assert len(snapshots_response.json()["items"]) >= 2
    assert runs_response.status_code == 200
    assert len(runs_response.json()["items"]) >= 2
    assert compare_response.status_code == 200
    assert compare_response.json()["overall_status"] in {"regressed", "mixed"}
    assert compare_response.json()["diagnosis"]


def test_documents_and_eval_run_report_endpoints(prepared_environment) -> None:
    from app.db.session import get_session_factory, init_database
    from app.main import app
    from app.services.ingestion import DocumentIngestionService

    init_database()
    session = get_session_factory()()
    try:
        DocumentIngestionService(session).import_directory(prepared_environment["docs_dir"])
        session.commit()
    finally:
        session.close()

    with TestClient(app) as client:
        documents_response = client.get("/v1/documents?limit=10")
        ask_response = client.post(
            "/v1/qa/ask",
            json={"query": "系统支持哪些核心能力？", "top_k": 3},
        )
        ask_payload = ask_response.json()
        chunk_response = client.get(
            f"/v1/documents/chunks/{ask_payload['citations'][0]['chunk_id']}?window=1"
        )
        document_response = client.get(
            f"/v1/documents/{chunk_response.json()['document_id']}"
        )
        datasets_response = client.get("/v1/evals/datasets")
        run_response = client.post(
            "/v1/evals/run",
            json={"dataset_name": "baseline_v1", "snapshot_name": "default"},
        )
        run_payload = run_response.json()
        report_response = client.get(
            f"/v1/evals/{run_payload['eval_run_id']}/report?format=markdown"
        )

    assert documents_response.status_code == 200
    assert documents_response.json()["items"]
    assert ask_response.status_code == 200
    assert chunk_response.status_code == 200
    assert document_response.status_code == 200
    assert chunk_response.json()["neighbors"]
    assert any(item["is_target"] for item in chunk_response.json()["neighbors"])
    assert document_response.json()["chunks"]
    assert datasets_response.status_code == 200
    assert "baseline_v1" in datasets_response.json()["items"]
    assert run_response.status_code == 200
    assert run_payload["report_markdown_path"].endswith("report.md")
    assert report_response.status_code == 200
    assert "# RAG QA Bench 评测报告" in report_response.json()["content"]


def test_eval_api_supports_replay_experiments(prepared_environment) -> None:
    from app.db.session import get_session_factory, init_database
    from app.main import app
    from app.services.ingestion import DocumentIngestionService

    init_database()
    session = get_session_factory()()
    try:
        DocumentIngestionService(session).import_directory(prepared_environment["docs_dir"])
        session.commit()
    finally:
        session.close()

    with TestClient(app) as client:
        base_response = client.post(
            "/v1/evals/replay-experiments",
            json={
                "case_name": "路线图双事实",
                "query": "路线图如何安排 PDF 和多知识库能力？",
                "snapshot_name": "compact_context",
                "top_k": 1,
            },
        )
        target_response = client.post(
            "/v1/evals/replay-experiments",
            json={
                "case_name": "路线图双事实",
                "query": "路线图如何安排 PDF 和多知识库能力？",
                "snapshot_name": "default",
                "top_k": 3,
                "retrieval_threshold": 0.12,
            },
        )
        base_payload = base_response.json()
        target_payload = target_response.json()
        list_response = client.get(
            "/v1/evals/replay-experiments",
            params={"limit": 10, "query": "路线图如何安排 PDF 和多知识库能力？"},
        )
        compare_response = client.get(
            "/v1/evals/replay-experiments/compare",
            params={
                "base_experiment_id": base_payload["experiment_id"],
                "target_experiment_id": target_payload["experiment_id"],
            },
        )

    assert base_response.status_code == 200
    assert target_response.status_code == 200
    assert list_response.status_code == 200
    assert compare_response.status_code == 200
    assert len(list_response.json()["items"]) >= 2
    assert target_payload["effective_settings"]["top_k"] == 3
    assert compare_response.json()["settings_diff"]["top_k"]["changed"] is True
    assert compare_response.json()["outcome"]["citation_count_delta"] > 0


def test_eval_api_returns_503_when_feature_disabled(prepared_environment, monkeypatch) -> None:
    monkeypatch.setenv("FEATURE_EVALS_ENABLED", "false")
    _reset_runtime_caches()

    from app.db.session import init_database
    from app.main import app

    init_database()

    with TestClient(app) as client:
        datasets_response = client.get("/v1/evals/datasets")
        latest_response = client.get("/v1/evals/latest")

    assert datasets_response.status_code == 503
    assert latest_response.status_code == 503
    assert "未启用评测与回归功能" in datasets_response.json()["detail"]
    assert "未启用评测与回归功能" in latest_response.json()["detail"]


def test_replay_api_returns_503_when_feature_disabled(prepared_environment, monkeypatch) -> None:
    monkeypatch.setenv("FEATURE_EVALS_ENABLED", "true")
    monkeypatch.setenv("FEATURE_REPLAY_EXPERIMENTS_ENABLED", "false")
    _reset_runtime_caches()

    from app.db.session import init_database
    from app.main import app

    init_database()

    with TestClient(app) as client:
        snapshots_response = client.get("/v1/evals/snapshots")
        replay_list_response = client.get("/v1/evals/replay-experiments?limit=10")
        replay_run_response = client.post(
            "/v1/evals/replay-experiments",
            json={
                "case_name": "路线图双事实",
                "query": "路线图如何安排 PDF 和多知识库能力？",
                "snapshot_name": "default",
            },
        )

    assert snapshots_response.status_code == 200
    assert replay_list_response.status_code == 503
    assert replay_run_response.status_code == 503
    assert "未启用回放实验功能" in replay_list_response.json()["detail"]
    assert "未启用回放实验功能" in replay_run_response.json()["detail"]


def test_root_page_serves_external_static_script(prepared_environment) -> None:
    from app.db.session import init_database
    from app.main import app

    init_database()

    with TestClient(app) as client:
        index_response = client.get("/")
        script_response = client.get("/static/index.js")
        workbench_response = client.get("/static/js/workbench.js")
        evals_response = client.get("/static/js/evals.js")
        eval_renderers_response = client.get("/static/js/eval-renderers.js")
        report_response = client.get("/static/js/report.js")

    assert index_response.status_code == 200
    assert '<script type="module" src="/static/index.js"></script>' in index_response.text
    assert 'id="report-outline-output"' in index_response.text
    assert 'id="report-restore-button"' in index_response.text
    assert script_response.status_code == 200
    assert 'from "./js/workbench.js"' in script_response.text
    assert "initializeWorkbench();" in script_response.text
    assert workbench_response.status_code == 200
    assert "export async function initializeWorkbench()" in workbench_response.text
    assert evals_response.status_code == 200
    assert "export function bindEvaluationHandlers" in evals_response.text
    assert eval_renderers_response.status_code == 200
    assert "export function renderCompare(payload)" in eval_renderers_response.text
    assert report_response.status_code == 200
    assert "export function syncReportPanel" in report_response.text
