from __future__ import annotations

import json
import math
from pathlib import Path
from statistics import mean
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.exceptions import NotFoundAppError
from app.db.models import EvalCase, EvalRun, ReplayExperiment
from app.repositories.rag import DocumentRepository, EvalRepository, ReplayExperimentRepository
from app.schemas.qa import Citation
from app.schemas.snapshots import EvalSnapshot
from app.services.qa import QAService


def percentile_95(values: list[float]) -> float:
    if not values:
        return 0.0
    sorted_values = sorted(values)
    index = max(math.ceil(len(sorted_values) * 0.95) - 1, 0)
    return round(sorted_values[index], 3)


class EvaluationService:
    def __init__(self, session: Session, settings: Optional[Settings] = None) -> None:
        self.session = session
        self.settings = settings or get_settings()
        self.eval_repo = EvalRepository(session)
        self.document_repo = DocumentRepository(session)
        self.replay_repo = ReplayExperimentRepository(session)

    def run(self, dataset_name: str, snapshot_name: str) -> EvalRun:
        snapshot = self.load_snapshot(snapshot_name)
        runtime_settings = self.settings.model_copy(update=snapshot.to_settings_update())
        cases = self.sync_cases_from_file(dataset_name)
        if not cases:
            raise NotFoundAppError(f"数据集不存在或为空: {dataset_name}")

        qa_service = QAService(self.session, runtime_settings)
        hit_scores: list[float] = []
        citation_scores: list[float] = []
        refusal_scores: list[float] = []
        grounded_scores: list[float] = []
        latencies: list[float] = []
        bad_cases: list[dict[str, object]] = []

        for case in cases:
            result = qa_service.ask(case.query, top_k=runtime_settings.top_k)
            latencies.append(self._latest_latency_ms(result.audit_id))
            expected_document_ids = set(case.expected_document_ids)
            expected_chunk_ids = set(case.expected_chunk_ids)
            retrieved_chunk_ids = [item.chunk_id for item in result.retrieved_chunks[:5]]
            retrieved_document_ids = [item.document_id for item in result.retrieved_chunks[:5]]

            if not case.should_refuse:
                hit = (
                    1.0
                    if expected_document_ids.intersection(retrieved_document_ids)
                    or expected_chunk_ids.intersection(retrieved_chunk_ids)
                    else 0.0
                )
                citation_precision = self._compute_citation_precision(
                    expected_document_ids=expected_document_ids,
                    expected_chunk_ids=expected_chunk_ids,
                    citations=result.citations,
                )
                grounded = self._compute_groundedness(
                    answer=result.answer,
                    refusal_reason=result.refusal_reason,
                    case=case,
                    citations=result.citations,
                )
                hit_scores.append(hit)
                citation_scores.append(citation_precision)
                grounded_scores.append(grounded)
            else:
                grounded_scores.append(1.0 if result.refusal_reason else 0.0)

            refusal_ok = (result.refusal_reason is not None) == case.should_refuse
            refusal_scores.append(1.0 if refusal_ok else 0.0)

            if (
                not case.should_refuse
                and (
                    not hit_scores
                    or hit_scores[-1] < 1.0
                    or citation_scores[-1] < 1.0
                    or grounded_scores[-1] < 1.0
                )
            ) or (case.should_refuse and not refusal_ok):
                bad_cases.append(
                    {
                        "case_name": case.name,
                        "audit_id": result.audit_id,
                        "query": case.query,
                        "answer": result.answer,
                        "refusal_reason": result.refusal_reason,
                        "expected_document_ids": case.expected_document_ids,
                        "expected_keywords": case.expected_keywords,
                    }
                )

        summary = {
            "hit@5": round(mean(hit_scores), 4) if hit_scores else 0.0,
            "citation_precision@3": round(mean(citation_scores), 4) if citation_scores else 0.0,
            "refusal_accuracy": round(mean(refusal_scores), 4) if refusal_scores else 0.0,
            "grounded_answer_rate": round(mean(grounded_scores), 4) if grounded_scores else 0.0,
            "latency_p95_ms": percentile_95(latencies),
        }
        eval_run = EvalRun(
            dataset_name=dataset_name,
            snapshot_name=snapshot_name,
            summary_json=summary,
            bad_cases_json=bad_cases,
            case_count=len(cases),
        )
        self.eval_repo.add_run(eval_run)
        self.session.commit()
        self.session.refresh(eval_run)
        self.write_report_files(
            eval_run=eval_run,
            snapshot=snapshot,
            runtime_settings=runtime_settings,
        )
        return eval_run

    def load_snapshot(self, snapshot_name: str) -> EvalSnapshot:
        snapshot_path = self.settings.eval_snapshots_path / f"{snapshot_name}.json"
        if not snapshot_path.exists():
            raise NotFoundAppError(f"评测快照不存在: {snapshot_path}")
        raw = json.loads(snapshot_path.read_text(encoding="utf-8"))
        raw.setdefault("name", snapshot_name)
        return EvalSnapshot.model_validate(raw)

    def get_report_paths(self, eval_run_id: str) -> dict[str, str]:
        report_dir = self.settings.eval_reports_path / eval_run_id
        return {
            "json": str((report_dir / "report.json").resolve()),
            "markdown": str((report_dir / "report.md").resolve()),
        }

    def get_compare_report_paths(
        self,
        base_eval_run_id: str,
        target_eval_run_id: str,
    ) -> dict[str, str]:
        report_dir = (
            self.settings.eval_reports_path
            / "compare"
            / f"{base_eval_run_id}__vs__{target_eval_run_id}"
        )
        return {
            "json": str((report_dir / "report.json").resolve()),
            "markdown": str((report_dir / "report.md").resolve()),
        }

    def write_report_files(
        self,
        eval_run: EvalRun,
        snapshot: EvalSnapshot,
        runtime_settings: Settings,
    ) -> None:
        report_paths = self.get_report_paths(eval_run.id)
        report_dir = Path(report_paths["json"]).parent
        report_dir.mkdir(parents=True, exist_ok=True)

        payload = {
            "eval_run_id": eval_run.id,
            "dataset_name": eval_run.dataset_name,
            "snapshot_name": eval_run.snapshot_name,
            "case_count": eval_run.case_count,
            "summary": eval_run.summary_json,
            "bad_cases": eval_run.bad_cases_json,
            "snapshot": snapshot.model_dump(),
            "runtime_settings": {
                "top_k": runtime_settings.top_k,
                "retrieval_candidate_k": runtime_settings.retrieval_candidate_k,
                "chunk_size": runtime_settings.chunk_size,
                "chunk_overlap": runtime_settings.chunk_overlap,
                "retrieval_threshold": runtime_settings.retrieval_threshold,
                "min_evidence_chunks": runtime_settings.min_evidence_chunks,
                "prompt_version": runtime_settings.prompt_version,
                "generator_model_name": runtime_settings.generator_model_name,
            },
            "created_at": eval_run.created_at.isoformat(),
        }
        Path(report_paths["json"]).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        Path(report_paths["markdown"]).write_text(
            self._build_markdown_report(payload),
            encoding="utf-8",
        )

    def compare_runs(self, base_eval_run_id: str, target_eval_run_id: str) -> dict[str, object]:
        base_run = self.get_by_id(base_eval_run_id)
        target_run = self.get_by_id(target_eval_run_id)

        metric_names = [
            "hit@5",
            "citation_precision@3",
            "refusal_accuracy",
            "grounded_answer_rate",
            "latency_p95_ms",
        ]
        metrics: dict[str, dict[str, object]] = {}
        for metric_name in metric_names:
            base_value = float(base_run.summary_json.get(metric_name, 0.0))
            target_value = float(target_run.summary_json.get(metric_name, 0.0))
            delta = round(target_value - base_value, 4)
            metrics[metric_name] = {
                "base": base_value,
                "target": target_value,
                "delta": delta,
                "status": self._classify_metric_change(metric_name, base_value, target_value),
            }

        base_case_names = {item["case_name"] for item in base_run.bad_cases_json}
        target_case_names = {item["case_name"] for item in target_run.bad_cases_json}
        bad_case_diff = {
            "new_regressions": sorted(target_case_names - base_case_names),
            "resolved": sorted(base_case_names - target_case_names),
            "persisted": sorted(base_case_names & target_case_names),
        }
        base_snapshot = self.load_snapshot(base_run.snapshot_name)
        target_snapshot = self.load_snapshot(target_run.snapshot_name)
        overall_status = self._classify_overall_status(metrics, bad_case_diff)
        comparison = {
            "base_eval_run_id": base_run.id,
            "target_eval_run_id": target_run.id,
            "base_snapshot_name": base_run.snapshot_name,
            "target_snapshot_name": target_run.snapshot_name,
            "base_dataset_name": base_run.dataset_name,
            "target_dataset_name": target_run.dataset_name,
            "base_snapshot_values": base_snapshot.to_settings_update(),
            "target_snapshot_values": target_snapshot.to_settings_update(),
            "metrics": metrics,
            "bad_case_diff": bad_case_diff,
            "diagnosis": self._build_comparison_diagnosis(
                metrics=metrics,
                bad_case_diff=bad_case_diff,
                base_snapshot=base_snapshot,
                target_snapshot=target_snapshot,
            ),
            "overall_status": overall_status,
        }
        self.write_compare_report_files(comparison)
        return comparison

    def write_compare_report_files(self, comparison: dict[str, object]) -> None:
        report_paths = self.get_compare_report_paths(
            comparison["base_eval_run_id"],
            comparison["target_eval_run_id"],
        )
        report_dir = Path(report_paths["json"]).parent
        report_dir.mkdir(parents=True, exist_ok=True)
        Path(report_paths["json"]).write_text(
            json.dumps(comparison, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        Path(report_paths["markdown"]).write_text(
            self._build_compare_markdown_report(comparison),
            encoding="utf-8",
        )

    def sync_cases_from_file(self, dataset_name: str) -> list[EvalCase]:
        dataset_path = self.settings.evals_path / f"{dataset_name}.json"
        if not dataset_path.exists():
            raise NotFoundAppError(f"评测数据集不存在: {dataset_path}")

        raw = json.loads(dataset_path.read_text(encoding="utf-8"))
        documents = {
            document.source_path: document.id for document in self.document_repo.list_all()
        }
        cases: list[EvalCase] = []
        for item in raw.get("cases", []):
            expected_document_ids = [
                documents[source_path]
                for source_path in item.get("expected_source_paths", [])
                if source_path in documents
            ]
            cases.append(
                EvalCase(
                    dataset_name=dataset_name,
                    name=item["name"],
                    query=item["query"],
                    should_refuse=bool(item.get("should_refuse", False)),
                    expected_document_ids=expected_document_ids,
                    expected_chunk_ids=item.get("expected_chunk_ids", []),
                    expected_keywords=item.get("expected_keywords", []),
                    forbidden_terms=item.get("forbidden_terms", []),
                )
            )
        self.eval_repo.replace_cases(dataset_name, cases)
        self.session.commit()
        return self.eval_repo.list_cases(dataset_name)

    def get_latest(self) -> EvalRun:
        latest = self.eval_repo.get_latest_run()
        if latest is None:
            raise NotFoundAppError("尚无评测结果")
        return latest

    def list_runs(self, limit: int = 10) -> list[EvalRun]:
        return self.eval_repo.list_runs(limit=limit)

    def list_snapshots(self) -> list[EvalSnapshot]:
        snapshot_dir = self.settings.eval_snapshots_path
        if not snapshot_dir.exists():
            return []
        snapshots: list[EvalSnapshot] = []
        for snapshot_path in sorted(snapshot_dir.glob("*.json")):
            raw = json.loads(snapshot_path.read_text(encoding="utf-8"))
            raw.setdefault("name", snapshot_path.stem)
            snapshots.append(EvalSnapshot.model_validate(raw))
        return snapshots

    def run_replay_experiment(
        self,
        query: str,
        case_name: Optional[str] = None,
        snapshot_name: str = "default",
        top_k: Optional[int] = None,
        retrieval_threshold: Optional[float] = None,
        source_eval_run_id: Optional[str] = None,
        source_snapshot_name: Optional[str] = None,
    ) -> dict[str, Any]:
        _, overrides, runtime_settings = self._build_replay_runtime_settings(
            snapshot_name=snapshot_name,
            top_k=top_k,
            retrieval_threshold=retrieval_threshold,
        )
        result = QAService(self.session, runtime_settings).ask(
            query=query,
            top_k=runtime_settings.top_k,
        )
        experiment = ReplayExperiment(
            case_name=case_name,
            query=query,
            source_eval_run_id=source_eval_run_id,
            source_snapshot_name=source_snapshot_name,
            snapshot_name=snapshot_name,
            overrides_json=overrides,
            effective_settings_json=self._extract_runtime_settings(runtime_settings),
            audit_id=result.audit_id,
            answer=result.answer,
            citations_json=[citation.model_dump() for citation in result.citations],
            confidence=result.confidence,
            refusal_reason=result.refusal_reason,
        )
        self.replay_repo.add(experiment)
        self.session.commit()
        self.session.refresh(experiment)
        return self._serialize_replay_experiment(experiment)

    def list_replay_experiments(
        self,
        limit: int = 20,
        query: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        return [
            self._serialize_replay_experiment(item)
            for item in self.replay_repo.list_recent(limit=limit, query=query)
        ]

    def get_replay_experiment(self, experiment_id: str) -> dict[str, Any]:
        experiment = self.replay_repo.get_by_id(experiment_id)
        if experiment is None:
            raise NotFoundAppError(f"回放实验不存在: {experiment_id}")
        return self._serialize_replay_experiment(experiment)

    def compare_replay_experiments(
        self,
        base_experiment_id: str,
        target_experiment_id: str,
    ) -> dict[str, Any]:
        base_experiment = self.get_replay_experiment(base_experiment_id)
        target_experiment = self.get_replay_experiment(target_experiment_id)
        settings_diff = self._build_settings_diff(
            base_experiment["effective_settings"],
            target_experiment["effective_settings"],
        )
        base_chunk_ids = {item["chunk_id"] for item in base_experiment["citations"]}
        target_chunk_ids = {item["chunk_id"] for item in target_experiment["citations"]}
        shared_chunk_ids = sorted(base_chunk_ids & target_chunk_ids)
        union_count = len(base_chunk_ids | target_chunk_ids)
        outcome = {
            "same_query": base_experiment["query"] == target_experiment["query"],
            "confidence_delta": round(
                float(target_experiment["confidence"]) - float(base_experiment["confidence"]),
                4,
            ),
            "citation_count_delta": len(target_chunk_ids) - len(base_chunk_ids),
            "citation_overlap": (
                round(len(shared_chunk_ids) / union_count, 4) if union_count else 1.0
            ),
            "shared_chunk_ids": shared_chunk_ids,
            "answer_changed": (
                base_experiment["answer"].strip() != target_experiment["answer"].strip()
            ),
            "refusal_changed": (
                base_experiment["refusal_reason"] != target_experiment["refusal_reason"]
            ),
        }
        diagnosis = self._build_replay_comparison_diagnosis(
            base_experiment=base_experiment,
            target_experiment=target_experiment,
            outcome=outcome,
        )
        overall_status = self._classify_replay_comparison_status(
            settings_diff=settings_diff,
            outcome=outcome,
        )
        return {
            "base_experiment": base_experiment,
            "target_experiment": target_experiment,
            "settings_diff": settings_diff,
            "outcome": outcome,
            "diagnosis": diagnosis,
            "overall_status": overall_status,
        }

    def list_datasets(self) -> list[str]:
        evals_dir = self.settings.evals_path
        if not evals_dir.exists():
            return []
        return [dataset_path.stem for dataset_path in sorted(evals_dir.glob("*.json"))]

    def read_report_content(
        self,
        eval_run_id: str,
        format_name: str = "markdown",
    ) -> dict[str, str]:
        self.get_by_id(eval_run_id)
        report_paths = self.get_report_paths(eval_run_id)
        if format_name not in {"markdown", "json"}:
            raise NotFoundAppError(f"不支持的报告格式: {format_name}")
        target_path = Path(report_paths["markdown" if format_name == "markdown" else "json"])
        if not target_path.exists():
            raise NotFoundAppError(f"报告文件不存在: {target_path}")
        return {
            "path": str(target_path.resolve()),
            "content": target_path.read_text(encoding="utf-8"),
        }

    def get_by_id(self, eval_run_id: str) -> EvalRun:
        eval_run = self.eval_repo.get_run_by_id(eval_run_id)
        if eval_run is None:
            raise NotFoundAppError(f"评测结果不存在: {eval_run_id}")
        return eval_run

    def _compute_citation_precision(
        self, expected_document_ids: set[str], expected_chunk_ids: set[str], citations
    ) -> float:
        if not citations:
            return 0.0
        hits = 0
        for citation in citations[:3]:
            if (
                citation.document_id in expected_document_ids
                or citation.chunk_id in expected_chunk_ids
            ):
                hits += 1
        return round(hits / min(len(citations[:3]), 3), 4)

    def _compute_groundedness(
        self,
        answer: str,
        refusal_reason: Optional[str],
        case: EvalCase,
        citations,
    ) -> float:
        if refusal_reason:
            return 0.0
        answer_lower = answer.lower()
        keywords = [keyword.lower() for keyword in case.expected_keywords]
        forbidden_terms = [keyword.lower() for keyword in case.forbidden_terms]
        keyword_ok = True if not keywords else all(keyword in answer_lower for keyword in keywords)
        forbidden_ok = all(term not in answer_lower for term in forbidden_terms)
        citation_ok = bool(citations) and any(
            citation.document_id in set(case.expected_document_ids) for citation in citations
        )
        return 1.0 if keyword_ok and forbidden_ok and citation_ok else 0.0

    def _latest_latency_ms(self, audit_id: str) -> float:
        from sqlalchemy import select

        from app.db.models import AnswerRun

        statement = select(AnswerRun).where(AnswerRun.id == audit_id)
        answer_run = self.session.scalar(statement)
        return float(answer_run.latency_ms if answer_run else 0.0)

    def _build_markdown_report(self, payload: dict[str, object]) -> str:
        summary = payload["summary"]
        snapshot = payload["snapshot"]
        runtime_settings = payload["runtime_settings"]
        bad_cases = payload["bad_cases"]

        lines = [
            "# RAG QA Bench 评测报告",
            "",
            f"- 评测运行 ID：`{payload['eval_run_id']}`",
            f"- 数据集：`{payload['dataset_name']}`",
            f"- 快照：`{payload['snapshot_name']}`",
            f"- 用例数：`{payload['case_count']}`",
            f"- 生成时间：`{payload['created_at']}`",
            "",
            "## 指标摘要",
            "",
        ]
        for key, value in summary.items():
            lines.append(f"- `{key}`：`{value}`")

        lines.extend(
            [
                "",
                "## 快照配置",
                "",
                f"- 名称：`{snapshot['name']}`",
                f"- 描述：{snapshot.get('description', '') or '无'}",
                "",
                "## 运行时参数",
                "",
            ]
        )
        for key, value in runtime_settings.items():
            lines.append(f"- `{key}`：`{value}`")

        lines.extend(["", "## Bad Cases", ""])
        if not bad_cases:
            lines.append("- 无")
            return "\n".join(lines) + "\n"

        for index, item in enumerate(bad_cases, start=1):
            lines.extend(
                [
                    f"### {index}. {item['case_name']}",
                    "",
                    f"- 审计 ID：`{item.get('audit_id') or '无'}`",
                    f"- 问题：{item['query']}",
                    f"- 拒答原因：{item.get('refusal_reason') or '无'}",
                    f"- 期望关键词：`{', '.join(item.get('expected_keywords', [])) or '无'}`",
                    f"- 回答：{item.get('answer') or '空'}",
                    "",
                ]
            )
        return "\n".join(lines) + "\n"

    def _build_compare_markdown_report(self, comparison: dict[str, object]) -> str:
        metrics = comparison["metrics"]
        bad_case_diff = comparison["bad_case_diff"]
        lines = [
            "# RAG QA Bench 对比报告",
            "",
            f"- 基线运行：`{comparison['base_eval_run_id']}`",
            f"- 对比运行：`{comparison['target_eval_run_id']}`",
            f"- 基线快照：`{comparison['base_snapshot_name']}`",
            f"- 对比快照：`{comparison['target_snapshot_name']}`",
            f"- 结论：`{comparison['overall_status']}`",
            "",
            "## 指标变化",
            "",
        ]
        for metric_name, item in metrics.items():
            lines.append(
                f"- `{metric_name}`：基线 `{item['base']}` -> 对比 `{item['target']}` "
                f"(delta `{item['delta']}`，状态 `{item['status']}`)"
            )

        lines.extend(
            [
                "",
                "## 归因提示",
                "",
            ]
        )
        diagnosis = comparison.get("diagnosis", [])
        if diagnosis:
            for item in diagnosis:
                lines.append(f"- {item}")
        else:
            lines.append("- 暂无明显归因提示")

        lines.extend(
            [
                "",
                "## Bad Case 变化",
                "",
                f"- 新增回归：`{', '.join(bad_case_diff['new_regressions']) or '无'}`",
                f"- 已解决：`{', '.join(bad_case_diff['resolved']) or '无'}`",
                f"- 持续存在：`{', '.join(bad_case_diff['persisted']) or '无'}`",
                "",
            ]
        )
        return "\n".join(lines) + "\n"

    def _build_replay_runtime_settings(
        self,
        snapshot_name: str,
        top_k: Optional[int] = None,
        retrieval_threshold: Optional[float] = None,
    ) -> tuple[EvalSnapshot, dict[str, Any], Settings]:
        snapshot = self.load_snapshot(snapshot_name)
        overrides: dict[str, Any] = {}
        if top_k is not None:
            overrides["top_k"] = top_k
        if retrieval_threshold is not None:
            overrides["retrieval_threshold"] = round(retrieval_threshold, 4)
        runtime_settings = self.settings.model_copy(
            update={
                **snapshot.to_settings_update(),
                **overrides,
            }
        )
        return snapshot, overrides, runtime_settings

    def _extract_runtime_settings(self, runtime_settings: Settings) -> dict[str, Any]:
        return {
            "top_k": runtime_settings.top_k,
            "retrieval_candidate_k": runtime_settings.retrieval_candidate_k,
            "chunk_size": runtime_settings.chunk_size,
            "chunk_overlap": runtime_settings.chunk_overlap,
            "retrieval_threshold": runtime_settings.retrieval_threshold,
            "min_evidence_chunks": runtime_settings.min_evidence_chunks,
            "prompt_version": runtime_settings.prompt_version,
            "generator_model_name": runtime_settings.generator_model_name,
        }

    def _serialize_replay_experiment(self, experiment: ReplayExperiment) -> dict[str, Any]:
        citations = [
            Citation.model_validate(item).model_dump()
            for item in experiment.citations_json
        ]
        return {
            "experiment_id": experiment.id,
            "case_name": experiment.case_name,
            "query": experiment.query,
            "snapshot_name": experiment.snapshot_name,
            "source_eval_run_id": experiment.source_eval_run_id,
            "source_snapshot_name": experiment.source_snapshot_name,
            "audit_id": experiment.audit_id,
            "answer": experiment.answer,
            "citations": citations,
            "confidence": experiment.confidence,
            "refusal_reason": experiment.refusal_reason,
            "overrides": experiment.overrides_json,
            "effective_settings": experiment.effective_settings_json,
            "created_at": experiment.created_at,
        }

    def _build_settings_diff(
        self,
        base_values: dict[str, Any],
        target_values: dict[str, Any],
    ) -> dict[str, dict[str, Any]]:
        payload: dict[str, dict[str, Any]] = {}
        for key in sorted(set(base_values) | set(target_values)):
            base_value = base_values.get(key)
            target_value = target_values.get(key)
            payload[key] = {
                "base": base_value,
                "target": target_value,
                "changed": base_value != target_value,
            }
        return payload

    def _classify_replay_comparison_status(
        self,
        settings_diff: dict[str, dict[str, Any]],
        outcome: dict[str, Any],
    ) -> str:
        if any(item["changed"] for item in settings_diff.values()):
            return "changed"
        if any(
            bool(outcome[key])
            for key in ("answer_changed", "refusal_changed")
        ):
            return "changed"
        if outcome["citation_count_delta"] != 0:
            return "changed"
        if abs(float(outcome["confidence_delta"])) > 0.001:
            return "changed"
        return "unchanged"

    def _build_replay_comparison_diagnosis(
        self,
        base_experiment: dict[str, Any],
        target_experiment: dict[str, Any],
        outcome: dict[str, Any],
    ) -> list[str]:
        messages: list[str] = []
        base_settings = base_experiment["effective_settings"]
        target_settings = target_experiment["effective_settings"]
        base_top_k = int(base_settings.get("top_k", self.settings.top_k))
        target_top_k = int(target_settings.get("top_k", self.settings.top_k))
        base_threshold = float(
            base_settings.get("retrieval_threshold", self.settings.retrieval_threshold)
        )
        target_threshold = float(
            target_settings.get("retrieval_threshold", self.settings.retrieval_threshold)
        )

        if not outcome["same_query"]:
            messages.append("两次实验问题不同，当前对比更适合做界面对照，不适合做参数归因。")
        if target_top_k > base_top_k and outcome["citation_count_delta"] > 0:
            messages.append("目标实验放宽了 top_k，可用于回答的证据片段数量随之增加。")
        if target_top_k < base_top_k and outcome["citation_count_delta"] < 0:
            messages.append("目标实验收紧了 top_k，引用数量下降更像是上下文窗口被压缩。")
        if (
            target_threshold > base_threshold
            and outcome["refusal_changed"]
            and target_experiment["refusal_reason"]
        ):
            messages.append("目标实验提高了拒答阈值，结果从作答切换成了拒答。")
        if (
            target_threshold < base_threshold
            and outcome["refusal_changed"]
            and not target_experiment["refusal_reason"]
        ):
            messages.append("目标实验降低了拒答阈值，结果从拒答切换成了作答。")
        if outcome["answer_changed"] and outcome["citation_overlap"] < 0.5:
            messages.append("两次实验的引用片段重叠较低，答案变化更像是证据组合发生了切换。")
        if not messages:
            if self._classify_replay_comparison_status(
                settings_diff=self._build_settings_diff(base_settings, target_settings),
                outcome=outcome,
            ) == "changed":
                messages.append("实验结果已变化，建议继续对比审计详情里的检索分数和证据片段。")
            else:
                messages.append("两次实验输出基本一致，可以继续调整 top_k 或拒答阈值扩大差异。")
        return messages

    def _classify_metric_change(
        self,
        metric_name: str,
        base_value: float,
        target_value: float,
    ) -> str:
        delta = round(target_value - base_value, 4)
        tolerance = 50.0 if metric_name == "latency_p95_ms" else 0.001
        if abs(delta) <= tolerance:
            return "unchanged"
        if metric_name == "latency_p95_ms":
            return "improved" if target_value < base_value else "regressed"
        return "improved" if target_value > base_value else "regressed"

    def _classify_overall_status(
        self,
        metrics: dict[str, dict[str, object]],
        bad_case_diff: dict[str, list[str]],
    ) -> str:
        if bad_case_diff["new_regressions"]:
            return "regressed"
        statuses = [item["status"] for item in metrics.values()]
        if "regressed" in statuses and "improved" not in statuses:
            return "regressed"
        if "improved" in statuses and "regressed" not in statuses:
            return "improved"
        if "improved" in statuses and "regressed" in statuses:
            return "mixed"
        return "unchanged"

    def _build_comparison_diagnosis(
        self,
        metrics: dict[str, dict[str, object]],
        bad_case_diff: dict[str, list[str]],
        base_snapshot: EvalSnapshot,
        target_snapshot: EvalSnapshot,
    ) -> list[str]:
        messages: list[str] = []
        base_top_k = base_snapshot.top_k or self.settings.top_k
        target_top_k = target_snapshot.top_k or self.settings.top_k
        base_threshold = base_snapshot.retrieval_threshold or self.settings.retrieval_threshold
        target_threshold = (
            target_snapshot.retrieval_threshold or self.settings.retrieval_threshold
        )
        base_min_evidence = (
            base_snapshot.min_evidence_chunks or self.settings.min_evidence_chunks
        )
        target_min_evidence = (
            target_snapshot.min_evidence_chunks or self.settings.min_evidence_chunks
        )
        base_candidates = (
            base_snapshot.retrieval_candidate_k or self.settings.retrieval_candidate_k
        )
        target_candidates = (
            target_snapshot.retrieval_candidate_k or self.settings.retrieval_candidate_k
        )

        grounded_status = metrics["grounded_answer_rate"]["status"]
        refusal_status = metrics["refusal_accuracy"]["status"]
        hit_status = metrics["hit@5"]["status"]

        if target_top_k < base_top_k and grounded_status == "regressed":
            messages.append("目标快照缩小了上下文窗口，导致多事实问题更容易丢失关键证据。")
        if (
            target_threshold > base_threshold or target_min_evidence > base_min_evidence
        ) and refusal_status == "regressed":
            messages.append("目标快照提高了拒答门槛或最小证据数，出现了更保守的误拒答。")
        if target_candidates < base_candidates and hit_status == "regressed":
            messages.append("目标快照减少了候选召回数量，命中率下降更像是召回不足。")
        if not messages and bad_case_diff["new_regressions"]:
            messages.append(
                "新 bad case 已出现，但当前规则无法直接归因，建议回查检索分数和审计日志。"
            )

        return messages
