from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from app.schemas.qa import Citation


class EvalSummaryResponse(BaseModel):
    eval_run_id: str
    dataset_name: str
    snapshot_name: str
    case_count: int
    summary: dict[str, Any]
    report_json_path: str
    report_markdown_path: str
    created_at: datetime


class EvalRunResponse(EvalSummaryResponse):
    bad_cases: list[dict[str, Any]]


class EvalRunListItem(BaseModel):
    eval_run_id: str
    dataset_name: str
    snapshot_name: str
    case_count: int
    summary: dict[str, Any]
    created_at: datetime


class EvalRunListResponse(BaseModel):
    items: list[EvalRunListItem]


class SnapshotSummaryResponse(BaseModel):
    name: str
    description: str
    values: dict[str, Any]


class SnapshotListResponse(BaseModel):
    items: list[SnapshotSummaryResponse]


class EvalCompareResponse(BaseModel):
    base_eval_run_id: str
    target_eval_run_id: str
    base_snapshot_name: str
    target_snapshot_name: str
    base_dataset_name: str
    target_dataset_name: str
    base_snapshot_values: dict[str, Any]
    target_snapshot_values: dict[str, Any]
    metrics: dict[str, dict[str, Any]]
    bad_case_diff: dict[str, list[str]]
    diagnosis: list[str]
    overall_status: str
    report_json_path: str
    report_markdown_path: str


class EvalRunRequest(BaseModel):
    dataset_name: str
    snapshot_name: str = "default"


class EvalReportContentResponse(BaseModel):
    eval_run_id: str
    format: str
    path: str
    content: str


class EvalDatasetListResponse(BaseModel):
    items: list[str]


class ReplayExperimentRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    case_name: Optional[str] = None
    snapshot_name: str = "default"
    top_k: Optional[int] = Field(default=None, ge=1, le=5)
    retrieval_threshold: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    source_eval_run_id: Optional[str] = None
    source_snapshot_name: Optional[str] = None


class ReplayExperimentResponse(BaseModel):
    experiment_id: str
    case_name: Optional[str] = None
    query: str
    snapshot_name: str
    source_eval_run_id: Optional[str] = None
    source_snapshot_name: Optional[str] = None
    audit_id: str
    answer: str
    citations: list[Citation]
    confidence: float
    refusal_reason: Optional[str] = None
    overrides: dict[str, Any]
    effective_settings: dict[str, Any]
    created_at: datetime


class ReplayExperimentListResponse(BaseModel):
    items: list[ReplayExperimentResponse]


class ReplayExperimentCompareResponse(BaseModel):
    base_experiment: ReplayExperimentResponse
    target_experiment: ReplayExperimentResponse
    settings_diff: dict[str, dict[str, Any]]
    outcome: dict[str, Any]
    diagnosis: list[str]
    overall_status: str
