from __future__ import annotations

import math
import re
from dataclasses import dataclass
from statistics import mean
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.config import Settings, get_settings
from app.db.models import Chunk, Document
from app.db.types import get_embedding_storage_backend
from app.services.embeddings import get_embedding_provider

TERM_PATTERN = re.compile(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]+")
STOP_TERMS = {
    "系统",
    "支持",
    "什么",
    "哪些",
    "是否",
    "可以",
    "一下",
    "请问",
    "这个",
    "那个",
    "吗",
    "呢",
    "是",
    "的",
}


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right:
        return 0.0
    dot_product = sum(left_value * right_value for left_value, right_value in zip(left, right))
    left_norm = math.sqrt(sum(item * item for item in left))
    right_norm = math.sqrt(sum(item * item for item in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return max(min(dot_product / (left_norm * right_norm), 1.0), 0.0)


def extract_terms(text: str) -> set[str]:
    terms: set[str] = set()
    for token in TERM_PATTERN.findall(text.lower()):
        if re.match(r"^[\u4e00-\u9fff]+$", token):
            cleaned = token
            for stop_term in STOP_TERMS:
                cleaned = cleaned.replace(stop_term, " ")
            for piece in cleaned.split():
                if len(piece) == 1:
                    terms.add(piece)
                elif len(piece) == 2:
                    terms.add(piece)
                else:
                    terms.update(piece[index : index + 2] for index in range(len(piece) - 1))
        else:
            terms.add(token)
    return {term for term in terms if term and term not in STOP_TERMS}


def compute_keyword_overlap(query: str, chunk_text: str, title_path: str) -> float:
    query_terms = extract_terms(query)
    if not query_terms:
        return 0.0
    context_terms = extract_terms(f"{title_path}\n{chunk_text}")
    if not context_terms:
        return 0.0
    matched = len(query_terms & context_terms)
    return matched / len(query_terms)


def build_pgvector_distance_expression(query_vector: list[float]):
    try:
        return Chunk.embedding.cosine_distance(query_vector)
    except AttributeError:
        return None


@dataclass
class RetrievedChunk:
    chunk_id: str
    document_id: str
    document_title: str
    title_path: str
    text: str
    vector_score: float
    keyword_score: float
    score: float


@dataclass
class EvidenceAssessment:
    confidence: float
    refusal_reason: Optional[str]
    failure_stage: Optional[str]
    effective_chunk_count: int
    keyword_match: bool
    avg_top_score: float


class ExactRetriever:
    """小规模语料的精确检索服务。"""

    def __init__(self, session: Session, settings: Optional[Settings] = None) -> None:
        self.session = session
        self.settings = settings or get_settings()
        self.embedding_provider = get_embedding_provider()

    def search(self, query: str, limit: Optional[int] = None) -> list[RetrievedChunk]:
        candidate_limit = limit or self.settings.retrieval_candidate_k
        query_vector = self.embedding_provider.embed_texts([query])[0]
        candidates = self._load_candidates(
            query_vector=query_vector, limit=max(candidate_limit * 2, 10)
        )
        reranked: list[RetrievedChunk] = []
        for chunk, document, vector_score in candidates:
            keyword_score = compute_keyword_overlap(query, chunk.text, chunk.title_path)
            score = round(min(1.0, vector_score * 0.65 + keyword_score * 0.35), 4)
            reranked.append(
                RetrievedChunk(
                    chunk_id=chunk.id,
                    document_id=document.id,
                    document_title=document.title,
                    title_path=chunk.title_path,
                    text=chunk.text,
                    vector_score=round(vector_score, 4),
                    keyword_score=round(keyword_score, 4),
                    score=score,
                )
            )
        reranked.sort(key=lambda item: item.score, reverse=True)
        return reranked[:candidate_limit]

    def _load_candidates(
        self, query_vector: list[float], limit: int
    ) -> list[tuple[Chunk, Document, float]]:
        bind = self.session.get_bind()
        storage_backend = (
            get_embedding_storage_backend(bind.dialect.name) if bind is not None else "json"
        )
        if bind is not None and bind.dialect.name == "postgresql" and storage_backend == "pgvector":
            distance = build_pgvector_distance_expression(query_vector)
            if distance is not None:
                statement = (
                    select(Chunk, Document, (1 - distance).label("vector_score"))
                    .join(Document, Chunk.document_id == Document.id)
                    .where(Chunk.embedding.is_not(None))
                    .order_by(distance)
                    .limit(limit)
                )
                rows = self.session.execute(statement).all()
                return [(row[0], row[1], max(min(float(row[2]), 1.0), 0.0)) for row in rows]

        statement = (
            select(Chunk).options(joinedload(Chunk.document)).where(Chunk.embedding.is_not(None))
        )
        chunks = list(self.session.scalars(statement))
        scored: list[tuple[Chunk, Document, float]] = []
        for chunk in chunks:
            if chunk.embedding is None or chunk.document is None:
                continue
            score = cosine_similarity(chunk.embedding, query_vector)
            scored.append((chunk, chunk.document, round(score, 4)))
        scored.sort(key=lambda item: item[2], reverse=True)
        return scored[:limit]


def assess_evidence(
    retrieved_chunks: list[RetrievedChunk],
    settings: Optional[Settings] = None,
) -> EvidenceAssessment:
    configured = settings or get_settings()
    if not retrieved_chunks:
        return EvidenceAssessment(
            confidence=0.0,
            refusal_reason="no_evidence",
            failure_stage="retrieval_empty",
            effective_chunk_count=0,
            keyword_match=False,
            avg_top_score=0.0,
        )

    scores = [chunk.score for chunk in retrieved_chunks[:3]]
    avg_top_score = mean(scores)
    top1_score = retrieved_chunks[0].score
    top2_score = retrieved_chunks[1].score if len(retrieved_chunks) > 1 else 0.0
    score_gap = max(top1_score - top2_score, 0.0)
    effective_chunk_count = len(
        [chunk for chunk in retrieved_chunks if chunk.score >= configured.retrieval_threshold * 0.8]
    )
    keyword_match = any(chunk.keyword_score >= 0.1 for chunk in retrieved_chunks[:5])
    top1_threshold = configured.retrieval_threshold * (0.9 if keyword_match else 1.0)

    confidence = (
        min(top1_score, 1.0) * 0.35
        + min(avg_top_score, 1.0) * 0.25
        + min(score_gap / 0.35, 1.0) * 0.15
        + min(effective_chunk_count / max(configured.min_evidence_chunks, 3), 1.0) * 0.15
        + (0.1 if keyword_match else 0.0)
    )
    confidence = round(min(max(confidence, 0.0), 1.0), 4)

    if top1_score < top1_threshold:
        return EvidenceAssessment(
            confidence=confidence,
            refusal_reason="low_confidence",
            failure_stage="retrieval_low_confidence",
            effective_chunk_count=effective_chunk_count,
            keyword_match=keyword_match,
            avg_top_score=round(avg_top_score, 4),
        )
    if avg_top_score < configured.retrieval_threshold * 0.75:
        return EvidenceAssessment(
            confidence=confidence,
            refusal_reason="low_confidence",
            failure_stage="retrieval_low_confidence",
            effective_chunk_count=effective_chunk_count,
            keyword_match=keyword_match,
            avg_top_score=round(avg_top_score, 4),
        )
    if effective_chunk_count < configured.min_evidence_chunks:
        return EvidenceAssessment(
            confidence=confidence,
            refusal_reason="insufficient_evidence",
            failure_stage="retrieval_low_confidence",
            effective_chunk_count=effective_chunk_count,
            keyword_match=keyword_match,
            avg_top_score=round(avg_top_score, 4),
        )
    if not keyword_match:
        return EvidenceAssessment(
            confidence=confidence,
            refusal_reason="keyword_mismatch",
            failure_stage="retrieval_low_confidence",
            effective_chunk_count=effective_chunk_count,
            keyword_match=keyword_match,
            avg_top_score=round(avg_top_score, 4),
        )

    return EvidenceAssessment(
        confidence=confidence,
        refusal_reason=None,
        failure_stage=None,
        effective_chunk_count=effective_chunk_count,
        keyword_match=keyword_match,
        avg_top_score=round(avg_top_score, 4),
    )
