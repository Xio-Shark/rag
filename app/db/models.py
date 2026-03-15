from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.config import get_settings
from app.db.base import Base
from app.db.types import EmbeddingVector


def make_uuid() -> str:
    return str(uuid.uuid4())


EMBEDDING_DIMENSIONS = get_settings().embedding_dimensions


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=make_uuid)
    source_path: Mapped[str] = mapped_column(String(1024), unique=True, nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    file_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ready")
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    content_chars: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    chunks: Mapped[list["Chunk"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="Chunk.sequence",
    )


class Chunk(Base):
    __tablename__ = "chunks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=make_uuid)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    title_path: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    text: Mapped[str] = mapped_column(Text, nullable=False)
    char_count: Mapped[int] = mapped_column(Integer, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    embedding: Mapped[Optional[list[float]]] = mapped_column(
        EmbeddingVector(EMBEDDING_DIMENSIONS),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    document: Mapped[Document] = relationship(back_populates="chunks")


class AnswerRun(Base):
    __tablename__ = "answer_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=make_uuid)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False, default="")
    citations_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    refusal_reason: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    prompt_version: Mapped[str] = mapped_column(String(64), nullable=False)
    generator_model: Mapped[str] = mapped_column(String(128), nullable=False)
    embedding_model: Mapped[str] = mapped_column(String(128), nullable=False)
    top_k: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_size: Mapped[int] = mapped_column(Integer, nullable=False)
    latency_ms: Mapped[float] = mapped_column(Float, nullable=False)
    token_usage: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cost: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    retrieved_chunk_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    retrieved_scores: Mapped[list[float]] = mapped_column(JSON, default=list)
    context_char_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failure_stage: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EvalCase(Base):
    __tablename__ = "eval_cases"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=make_uuid)
    dataset_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    should_refuse: Mapped[bool] = mapped_column(nullable=False, default=False)
    expected_document_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    expected_chunk_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    expected_keywords: Mapped[list[str]] = mapped_column(JSON, default=list)
    forbidden_terms: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EvalRun(Base):
    __tablename__ = "eval_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=make_uuid)
    dataset_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    snapshot_name: Mapped[str] = mapped_column(String(128), nullable=False)
    summary_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    bad_cases_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    case_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ReplayExperiment(Base):
    __tablename__ = "replay_experiments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=make_uuid)
    case_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    source_eval_run_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    source_snapshot_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    snapshot_name: Mapped[str] = mapped_column(String(128), nullable=False)
    overrides_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    effective_settings_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    audit_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    answer: Mapped[str] = mapped_column(Text, nullable=False, default="")
    citations_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    refusal_reason: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
