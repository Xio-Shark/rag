from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.api.deps import get_qa_service
from app.core.exceptions import NotFoundAppError, ValidationAppError
from app.core.observability import get_request_id, log_event
from app.schemas.qa import (
    AskRequest,
    AskResponse,
    AuditDetailResponse,
    AuditRunListResponse,
)
from app.services.qa import QAService

router = APIRouter(prefix="/qa", tags=["qa"])


@router.post("/ask", response_model=AskResponse)
def ask_question(
    payload: AskRequest,
    request: Request,
    service: QAService = Depends(get_qa_service),
) -> AskResponse:
    try:
        result = service.ask(query=payload.query, top_k=payload.top_k)
    except ValidationAppError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    response = AskResponse(
        answer=result.answer,
        citations=result.citations,
        confidence=result.confidence,
        refusal_reason=result.refusal_reason,
        audit_id=result.audit_id,
    )
    log_event(
        "qa.ask.completed",
        request_id=get_request_id(request),
        audit_id=result.audit_id,
        citation_count=len(result.citations),
        confidence=result.confidence,
        refused=result.refusal_reason is not None,
    )
    return response


@router.get("/runs", response_model=AuditRunListResponse)
def list_audit_runs(
    limit: int = Query(default=20, ge=1, le=50),
    service: QAService = Depends(get_qa_service),
) -> AuditRunListResponse:
    return AuditRunListResponse(items=service.list_recent_audits(limit=limit))


@router.get("/runs/{audit_id}", response_model=AuditDetailResponse)
def get_audit_detail(
    audit_id: str,
    service: QAService = Depends(get_qa_service),
) -> AuditDetailResponse:
    try:
        return service.get_audit_detail(audit_id)
    except NotFoundAppError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
