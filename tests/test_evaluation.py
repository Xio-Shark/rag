from app.core.config import get_settings
from app.services.evaluation import EvaluationService
from app.services.qa import QAService


def test_evaluation_service_runs_and_returns_summary(db_session) -> None:
    service = EvaluationService(db_session)
    eval_run = service.run(dataset_name="baseline_v1", snapshot_name="default")
    report_paths = service.get_report_paths(eval_run.id)

    assert eval_run.case_count == 4
    assert "hit@5" in eval_run.summary_json
    assert "grounded_answer_rate" in eval_run.summary_json
    assert eval_run.summary_json["grounded_answer_rate"] == 1.0
    assert eval_run.bad_cases_json == []
    assert report_paths["json"].endswith("report.json")
    assert report_paths["markdown"].endswith("report.md")


def test_evaluation_service_can_compare_runs(db_session) -> None:
    service = EvaluationService(db_session)
    base_run = service.run(dataset_name="baseline_v1", snapshot_name="default")
    target_run = service.run(dataset_name="baseline_v1", snapshot_name="compact_context")
    comparison = service.compare_runs(base_run.id, target_run.id)
    report_paths = service.get_compare_report_paths(base_run.id, target_run.id)

    assert comparison["base_eval_run_id"] == base_run.id
    assert comparison["target_eval_run_id"] == target_run.id
    assert comparison["overall_status"] in {"regressed", "mixed"}
    assert comparison["metrics"]["grounded_answer_rate"]["delta"] < 0
    assert comparison["diagnosis"]
    assert "上下文窗口" in comparison["diagnosis"][0]
    assert target_run.bad_cases_json
    assert target_run.bad_cases_json[0]["audit_id"]
    assert report_paths["json"].endswith("report.json")
    assert report_paths["markdown"].endswith("report.md")


def test_qa_service_uses_runtime_top_k_for_multi_fact_question(db_session) -> None:
    settings = get_settings()
    compact_settings = settings.model_copy(update={"top_k": 1})
    default_settings = settings.model_copy(update={"top_k": 3})

    compact_result = QAService(db_session, compact_settings).ask(
        "路线图如何安排 PDF 和多知识库能力？"
    )
    default_result = QAService(db_session, default_settings).ask(
        "路线图如何安排 PDF 和多知识库能力？"
    )

    assert len(compact_result.citations) == 1
    assert len(default_result.citations) >= 2


def test_default_snapshot_avoids_weakly_related_v11_evidence(db_session) -> None:
    result = QAService(db_session, get_settings()).ask("后续版本会扩展哪些能力？")

    assert result.refusal_reason is None
    assert "多知识库" in result.answer
    assert "在线反馈" in result.answer
    assert "复杂表格抽取" not in result.answer


def test_evaluation_service_creates_replay_experiment_with_overrides(db_session) -> None:
    service = EvaluationService(db_session)

    experiment = service.run_replay_experiment(
        query="路线图如何安排 PDF 和多知识库能力？",
        case_name="路线图双事实",
        snapshot_name="compact_context",
        top_k=3,
        retrieval_threshold=0.12,
        source_snapshot_name="compact_context",
    )
    items = service.list_replay_experiments(
        limit=10,
        query="路线图如何安排 PDF 和多知识库能力？",
    )

    assert experiment["experiment_id"]
    assert experiment["snapshot_name"] == "compact_context"
    assert experiment["audit_id"]
    assert experiment["overrides"]["top_k"] == 3
    assert experiment["overrides"]["retrieval_threshold"] == 0.12
    assert experiment["effective_settings"]["top_k"] == 3
    assert experiment["effective_settings"]["retrieval_threshold"] == 0.12
    assert len(experiment["citations"]) >= 2
    assert items[0]["experiment_id"] == experiment["experiment_id"]


def test_evaluation_service_can_compare_replay_experiments(db_session) -> None:
    service = EvaluationService(db_session)
    base_experiment = service.run_replay_experiment(
        query="路线图如何安排 PDF 和多知识库能力？",
        case_name="路线图双事实",
        snapshot_name="compact_context",
        top_k=1,
    )
    target_experiment = service.run_replay_experiment(
        query="路线图如何安排 PDF 和多知识库能力？",
        case_name="路线图双事实",
        snapshot_name="default",
        top_k=3,
    )

    comparison = service.compare_replay_experiments(
        base_experiment_id=base_experiment["experiment_id"],
        target_experiment_id=target_experiment["experiment_id"],
    )

    assert comparison["base_experiment"]["experiment_id"] == base_experiment["experiment_id"]
    assert comparison["target_experiment"]["experiment_id"] == target_experiment["experiment_id"]
    assert comparison["settings_diff"]["top_k"]["changed"] is True
    assert comparison["outcome"]["citation_count_delta"] > 0
    assert comparison["diagnosis"]
