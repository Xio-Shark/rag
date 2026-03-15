from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.api.deps import get_evaluation_service, require_feature_enabled
from app.core.exceptions import NotFoundAppError
from app.core.observability import get_request_id, log_event
from app.schemas.evals import (
    EvalCompareResponse,
    EvalDatasetListResponse,
    EvalReportContentResponse,
    EvalRunListItem,
    EvalRunListResponse,
    EvalRunRequest,
    EvalRunResponse,
    EvalSummaryResponse,
    ReplayExperimentCompareResponse,
    ReplayExperimentListResponse,
    ReplayExperimentRequest,
    ReplayExperimentResponse,
    SnapshotListResponse,
    SnapshotSummaryResponse,
)
from app.services.evaluation import EvaluationService

router = APIRouter(prefix="/evals", tags=["evals"])
require_evals_feature = require_feature_enabled("evals")
require_replay_feature = require_feature_enabled("replay_experiments")


@router.get("/latest", response_model=EvalSummaryResponse)
def get_latest_eval(
    _: None = Depends(require_evals_feature),
    service: EvaluationService = Depends(get_evaluation_service),
) -> EvalSummaryResponse:
    try:
        eval_run = service.get_latest()
    except NotFoundAppError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    report_paths = service.get_report_paths(eval_run.id)
    return EvalSummaryResponse(
        eval_run_id=eval_run.id,
        dataset_name=eval_run.dataset_name,
        snapshot_name=eval_run.snapshot_name,
        case_count=eval_run.case_count,
        summary=eval_run.summary_json,
        report_json_path=report_paths["json"],
        report_markdown_path=report_paths["markdown"],
        created_at=eval_run.created_at,
    )


@router.get("/runs", response_model=EvalRunListResponse)
def list_eval_runs(
    limit: int = Query(default=10, ge=1, le=50),
    _: None = Depends(require_evals_feature),
    service: EvaluationService = Depends(get_evaluation_service),
) -> EvalRunListResponse:
    runs = service.list_runs(limit=limit)
    return EvalRunListResponse(
        items=[
            EvalRunListItem(
                eval_run_id=eval_run.id,
                dataset_name=eval_run.dataset_name,
                snapshot_name=eval_run.snapshot_name,
                case_count=eval_run.case_count,
                summary=eval_run.summary_json,
                created_at=eval_run.created_at,
            )
            for eval_run in runs
        ]
    )


@router.get("/snapshots", response_model=SnapshotListResponse)
def list_snapshots(
    _: None = Depends(require_evals_feature),
    service: EvaluationService = Depends(get_evaluation_service),
) -> SnapshotListResponse:
    snapshots = service.list_snapshots()
    return SnapshotListResponse(
        items=[
            SnapshotSummaryResponse(
                name=snapshot.name,
                description=snapshot.description,
                values=snapshot.to_settings_update(),
            )
            for snapshot in snapshots
        ]
    )


@router.get("/datasets", response_model=EvalDatasetListResponse)
def list_datasets(
    _: None = Depends(require_evals_feature),
    service: EvaluationService = Depends(get_evaluation_service),
) -> EvalDatasetListResponse:
    return EvalDatasetListResponse(items=service.list_datasets())


@router.get("/replay-experiments", response_model=ReplayExperimentListResponse)
def list_replay_experiments(
    limit: int = Query(default=20, ge=1, le=50),
    query: Optional[str] = Query(default=None),
    _: None = Depends(require_replay_feature),
    service: EvaluationService = Depends(get_evaluation_service),
) -> ReplayExperimentListResponse:
    return ReplayExperimentListResponse(
        items=service.list_replay_experiments(limit=limit, query=query)
    )


@router.post("/replay-experiments", response_model=ReplayExperimentResponse)
def run_replay_experiment(
    payload: ReplayExperimentRequest,
    request: Request,
    _: None = Depends(require_replay_feature),
    service: EvaluationService = Depends(get_evaluation_service),
) -> ReplayExperimentResponse:
    try:
        result = service.run_replay_experiment(
            query=payload.query,
            case_name=payload.case_name,
            snapshot_name=payload.snapshot_name,
            top_k=payload.top_k,
            retrieval_threshold=payload.retrieval_threshold,
            source_eval_run_id=payload.source_eval_run_id,
            source_snapshot_name=payload.source_snapshot_name,
        )
    except NotFoundAppError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    response = ReplayExperimentResponse(**result)
    log_event(
        "eval.replay.completed",
        request_id=get_request_id(request),
        experiment_id=result["experiment_id"],
        audit_id=result["audit_id"],
        snapshot_name=result["snapshot_name"],
        source_eval_run_id=result.get("source_eval_run_id"),
    )
    return response


@router.get(
    "/replay-experiments/compare",
    response_model=ReplayExperimentCompareResponse,
)
def compare_replay_experiments(
    base_experiment_id: str = Query(...),
    target_experiment_id: str = Query(...),
    _: None = Depends(require_replay_feature),
    service: EvaluationService = Depends(get_evaluation_service),
) -> ReplayExperimentCompareResponse:
    try:
        comparison = service.compare_replay_experiments(
            base_experiment_id=base_experiment_id,
            target_experiment_id=target_experiment_id,
        )
    except NotFoundAppError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return ReplayExperimentCompareResponse(**comparison)


@router.post("/run", response_model=EvalRunResponse)
def run_eval(
    payload: EvalRunRequest,
    request: Request,
    _: None = Depends(require_evals_feature),
    service: EvaluationService = Depends(get_evaluation_service),
) -> EvalRunResponse:
    try:
        eval_run = service.run(
            dataset_name=payload.dataset_name,
            snapshot_name=payload.snapshot_name,
        )
    except NotFoundAppError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    report_paths = service.get_report_paths(eval_run.id)
    response = EvalRunResponse(
        eval_run_id=eval_run.id,
        dataset_name=eval_run.dataset_name,
        snapshot_name=eval_run.snapshot_name,
        case_count=eval_run.case_count,
        summary=eval_run.summary_json,
        report_json_path=report_paths["json"],
        report_markdown_path=report_paths["markdown"],
        bad_cases=eval_run.bad_cases_json,
        created_at=eval_run.created_at,
    )
    log_event(
        "eval.run.completed",
        request_id=get_request_id(request),
        eval_run_id=eval_run.id,
        dataset_name=eval_run.dataset_name,
        snapshot_name=eval_run.snapshot_name,
        case_count=eval_run.case_count,
    )
    return response


@router.get("/compare", response_model=EvalCompareResponse)
def compare_eval_runs(
    base_eval_run_id: str = Query(...),
    target_eval_run_id: str = Query(...),
    _: None = Depends(require_evals_feature),
    service: EvaluationService = Depends(get_evaluation_service),
) -> EvalCompareResponse:
    try:
        comparison = service.compare_runs(
            base_eval_run_id=base_eval_run_id,
            target_eval_run_id=target_eval_run_id,
        )
    except NotFoundAppError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    report_paths = service.get_compare_report_paths(
        base_eval_run_id=base_eval_run_id,
        target_eval_run_id=target_eval_run_id,
    )
    return EvalCompareResponse(
        **comparison,
        report_json_path=report_paths["json"],
        report_markdown_path=report_paths["markdown"],
    )


@router.get("/{eval_run_id}", response_model=EvalRunResponse)
def get_eval_by_id(
    eval_run_id: str,
    _: None = Depends(require_evals_feature),
    service: EvaluationService = Depends(get_evaluation_service),
) -> EvalRunResponse:
    try:
        eval_run = service.get_by_id(eval_run_id)
    except NotFoundAppError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    report_paths = service.get_report_paths(eval_run.id)
    return EvalRunResponse(
        eval_run_id=eval_run.id,
        dataset_name=eval_run.dataset_name,
        snapshot_name=eval_run.snapshot_name,
        case_count=eval_run.case_count,
        summary=eval_run.summary_json,
        report_json_path=report_paths["json"],
        report_markdown_path=report_paths["markdown"],
        bad_cases=eval_run.bad_cases_json,
        created_at=eval_run.created_at,
    )


@router.get("/{eval_run_id}/report", response_model=EvalReportContentResponse)
def get_eval_report_content(
    eval_run_id: str,
    format_name: str = Query(default="markdown", alias="format"),
    _: None = Depends(require_evals_feature),
    service: EvaluationService = Depends(get_evaluation_service),
) -> EvalReportContentResponse:
    try:
        report = service.read_report_content(
            eval_run_id=eval_run_id,
            format_name=format_name,
        )
    except NotFoundAppError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return EvalReportContentResponse(
        eval_run_id=eval_run_id,
        format=format_name,
        path=report["path"],
        content=report["content"],
    )
