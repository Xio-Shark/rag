from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class Citation(BaseModel):
    chunk_id: str
    document_id: str
    document_title: str
    title_path: str
    snippet: str
    score: float = Field(ge=0.0, le=1.0)


class AskRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    top_k: int = Field(default=3, ge=1, le=5)


class AskResponse(BaseModel):
    answer: str
    citations: list[Citation]
    confidence: float = Field(ge=0.0, le=1.0)
    refusal_reason: Optional[str] = None
    audit_id: str


class RetrievedChunkResponse(BaseModel):
    chunk_id: str
    document_id: str
    document_title: str
    title_path: str
    snippet: str
    score: float = Field(ge=0.0, le=1.0)


class AuditDetailResponse(BaseModel):
    audit_id: str
    query: str
    answer: str
    citations: list[Citation]
    retrieved_chunks: list[RetrievedChunkResponse]
    confidence: float = Field(ge=0.0, le=1.0)
    refusal_reason: Optional[str] = None
    failure_stage: Optional[str] = None
    prompt_version: str
    generator_model: str
    embedding_model: str
    top_k: int
    chunk_size: int
    latency_ms: float
    token_usage: int
    cost: float
    context_char_count: int
    created_at: datetime


class AuditRunListItem(BaseModel):
    audit_id: str
    query: str
    confidence: float = Field(ge=0.0, le=1.0)
    refusal_reason: Optional[str] = None
    failure_stage: Optional[str] = None
    latency_ms: float
    created_at: datetime


class AuditRunListResponse(BaseModel):
    items: list[AuditRunListItem]
