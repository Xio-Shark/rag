from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.api.deps import get_ingestion_service, get_settings_dep
from app.core.config import Settings
from app.core.exceptions import NotFoundAppError, ValidationAppError
from app.core.observability import get_request_id, log_event
from app.schemas.documents import (
    ChunkDetailResponse,
    DocumentDetailResponse,
    DocumentListResponse,
    ImportedDocumentSummary,
    ImportRequest,
    ImportResponse,
)
from app.services.ingestion import DocumentIngestionService

router = APIRouter(prefix="/documents", tags=["documents"])


def resolve_import_dir(requested: Optional[str], settings: Settings) -> Path:
    base = settings.docs_path
    if requested is None:
        return base

    candidate = Path(requested)
    if not candidate.is_absolute():
        candidate = (base / candidate).resolve()
    else:
        candidate = candidate.resolve()

    if candidate != base and base not in candidate.parents:
        raise ValidationAppError("导入目录必须位于 data/docs 之下")
    return candidate


@router.post("/import", response_model=ImportResponse)
def import_documents(
    payload: ImportRequest,
    request: Request,
    service: DocumentIngestionService = Depends(get_ingestion_service),
    settings: Settings = Depends(get_settings_dep),
) -> ImportResponse:
    try:
        source_dir = resolve_import_dir(payload.source_dir, settings)
        result = service.import_directory(source_dir=source_dir)
    except ValidationAppError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    response = ImportResponse(
        imported_count=result.imported_count,
        skipped_count=result.skipped_count,
        chunk_count=result.chunk_count,
        documents=[
            ImportedDocumentSummary(
                document_id=item.document_id,
                source_path=item.source_path,
                title="",
                status=item.status,
                chunk_count=item.chunk_count,
            )
            for item in result.documents
        ],
    )
    log_event(
        "documents.import.completed",
        request_id=get_request_id(request),
        source_dir=str(source_dir),
        imported_count=result.imported_count,
        skipped_count=result.skipped_count,
        chunk_count=result.chunk_count,
    )
    return response


@router.get("", response_model=DocumentListResponse)
def list_documents(
    limit: int = Query(default=20, ge=1, le=100),
    service: DocumentIngestionService = Depends(get_ingestion_service),
) -> DocumentListResponse:
    documents = service.list_documents(limit=limit)
    return DocumentListResponse(
        items=[
            ImportedDocumentSummary(
                document_id=document.id,
                source_path=document.source_path,
                title=document.title,
                status=document.status,
                chunk_count=document.chunk_count,
                file_type=document.file_type,
                content_chars=document.content_chars,
                created_at=document.created_at,
            )
            for document in documents
        ]
    )


@router.get("/{document_id}", response_model=DocumentDetailResponse)
def get_document_detail(
    document_id: str,
    service: DocumentIngestionService = Depends(get_ingestion_service),
) -> DocumentDetailResponse:
    try:
        return service.get_document_detail(document_id=document_id)
    except NotFoundAppError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/chunks/{chunk_id}", response_model=ChunkDetailResponse)
def get_chunk_detail(
    chunk_id: str,
    window: int = Query(default=1, ge=0, le=3),
    service: DocumentIngestionService = Depends(get_ingestion_service),
) -> ChunkDetailResponse:
    try:
        return service.get_chunk_detail(chunk_id=chunk_id, window=window)
    except NotFoundAppError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
