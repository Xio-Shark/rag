from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.exceptions import NotFoundAppError
from app.db.models import AnswerRun
from app.repositories.rag import AnswerRunRepository, ChunkRepository
from app.schemas.qa import (
    AuditDetailResponse,
    AuditRunListItem,
    Citation,
    RetrievedChunkResponse,
)
from app.services.generator import (
    ExtractiveAnswerGenerator,
    GenerationResult,
    get_answer_generator,
)
from app.services.retrieval import ExactRetriever, RetrievedChunk, assess_evidence, extract_terms


@dataclass
class QAResult:
    answer: str
    citations: list[Citation]
    confidence: float
    refusal_reason: Optional[str]
    audit_id: str
    retrieved_chunks: list[RetrievedChunk]


class QAService:
    def __init__(self, session: Session, settings: Optional[Settings] = None) -> None:
        self.session = session
        self.settings = settings or get_settings()
        self.retriever = ExactRetriever(session, self.settings)
        self.answer_run_repo = AnswerRunRepository(session)
        self.chunk_repo = ChunkRepository(session)

    def ask(self, query: str, top_k: Optional[int] = None) -> QAResult:
        started_at = time.perf_counter()
        final_top_k = top_k or self.settings.top_k
        retrieved = self.retriever.search(query=query, limit=self.settings.retrieval_candidate_k)
        evidence = assess_evidence(retrieved, self.settings)
        selected_chunks = self._select_citation_chunks(
            query=query,
            retrieved=retrieved,
            top_k=final_top_k,
        )
        citations = [self._to_citation(item) for item in selected_chunks]
        answer = ""
        refusal_reason = evidence.refusal_reason
        failure_stage = evidence.failure_stage
        token_usage = 0
        cost = 0.0
        generator_backend = getattr(
            get_answer_generator(self.settings), "backend_name", "extractive"
        )

        if refusal_reason is None:
            generation_result = self._generate_answer(query=query, citations=citations)
            answer = generation_result.answer
            refusal_reason = generation_result.refusal_reason
            token_usage = generation_result.token_usage
            cost = generation_result.cost
            generator_backend = generation_result.backend
            if generation_result.failure_stage is not None:
                failure_stage = generation_result.failure_stage

        latency_ms = round((time.perf_counter() - started_at) * 1000, 3)
        answer_run = AnswerRun(
            query=query,
            answer=answer,
            citations_json=[citation.model_dump() for citation in citations],
            confidence=evidence.confidence,
            refusal_reason=refusal_reason,
            prompt_version=self.settings.prompt_version,
            generator_model=generator_backend,
            embedding_model=self.settings.embedding_model_name,
            top_k=final_top_k,
            chunk_size=self.settings.chunk_size,
            latency_ms=latency_ms,
            token_usage=token_usage,
            cost=cost,
            retrieved_chunk_ids=[item.chunk_id for item in retrieved],
            retrieved_scores=[item.score for item in retrieved],
            context_char_count=sum(len(citation.snippet) for citation in citations),
            failure_stage=failure_stage,
        )
        self.answer_run_repo.add(answer_run)
        self.session.commit()
        self.session.refresh(answer_run)

        return QAResult(
            answer=answer,
            citations=citations if refusal_reason != "no_evidence" else [],
            confidence=evidence.confidence,
            refusal_reason=refusal_reason,
            audit_id=answer_run.id,
            retrieved_chunks=retrieved,
        )

    def get_audit_detail(self, audit_id: str) -> AuditDetailResponse:
        answer_run = self.answer_run_repo.get_by_id(audit_id)
        if answer_run is None:
            raise NotFoundAppError(f"问答审计不存在: {audit_id}")

        retrieved_chunks = self._load_retrieved_chunks(
            chunk_ids=answer_run.retrieved_chunk_ids,
            scores=answer_run.retrieved_scores,
        )
        citations = [Citation.model_validate(item) for item in answer_run.citations_json]

        return AuditDetailResponse(
            audit_id=answer_run.id,
            query=answer_run.query,
            answer=answer_run.answer,
            citations=citations,
            retrieved_chunks=retrieved_chunks,
            confidence=answer_run.confidence,
            refusal_reason=answer_run.refusal_reason,
            failure_stage=answer_run.failure_stage,
            prompt_version=answer_run.prompt_version,
            generator_model=answer_run.generator_model,
            embedding_model=answer_run.embedding_model,
            top_k=answer_run.top_k,
            chunk_size=answer_run.chunk_size,
            latency_ms=answer_run.latency_ms,
            token_usage=answer_run.token_usage,
            cost=answer_run.cost,
            context_char_count=answer_run.context_char_count,
            created_at=answer_run.created_at,
        )

    def list_recent_audits(self, limit: int = 20) -> list[AuditRunListItem]:
        return [
            AuditRunListItem(
                audit_id=answer_run.id,
                query=answer_run.query,
                confidence=answer_run.confidence,
                refusal_reason=answer_run.refusal_reason,
                failure_stage=answer_run.failure_stage,
                latency_ms=answer_run.latency_ms,
                created_at=answer_run.created_at,
            )
            for answer_run in self.answer_run_repo.list_recent(limit=limit)
        ]

    def _generate_answer(self, query: str, citations: list[Citation]) -> GenerationResult:
        generator = get_answer_generator(self.settings)
        citation_payload = [citation.model_dump() for citation in citations]
        try:
            return generator.generate(
                query=query, citations=citation_payload, settings=self.settings
            )
        except Exception as exc:
            fallback = ExtractiveAnswerGenerator()
            failure_stage = "generation_timeout"
            if "JSON" in str(exc):
                failure_stage = "generation_schema_error"
            result = fallback.generate(
                query=query, citations=citation_payload, settings=self.settings
            )
            result.failure_stage = failure_stage
            return result

    def _to_citation(self, item: RetrievedChunk) -> Citation:
        return Citation(
            chunk_id=item.chunk_id,
            document_id=item.document_id,
            document_title=item.document_title,
            title_path=item.title_path,
            snippet=item.text[:300],
            score=item.score,
        )

    def _select_citation_chunks(
        self,
        query: str,
        retrieved: list[RetrievedChunk],
        top_k: int,
    ) -> list[RetrievedChunk]:
        if not retrieved:
            return []

        dynamic_floor = max(self.settings.retrieval_threshold * 0.8, retrieved[0].score * 0.75)
        candidate_items = [item for item in retrieved if item.score >= dynamic_floor]
        if not candidate_items:
            return retrieved[:1]

        best_keyword_score = max(item.keyword_score for item in candidate_items)
        if best_keyword_score > 0:
            keyword_floor = max(0.05, round(best_keyword_score * 0.45, 4))
            filtered_items = [
                item for item in candidate_items if item.keyword_score >= keyword_floor
            ]
            if filtered_items:
                candidate_items = filtered_items

        query_terms = extract_terms(query)
        top_item = candidate_items[0]
        covered_terms = self._extract_chunk_terms(top_item) & query_terms
        selected_items = [top_item]

        for item in candidate_items[1:]:
            if len(selected_items) >= top_k:
                break
            item_terms = self._extract_chunk_terms(item) & query_terms
            new_terms = item_terms - covered_terms
            if item.document_id != top_item.document_id:
                is_weaker_alternative = (
                    item.keyword_score <= top_item.keyword_score and item.score <= top_item.score
                )
                if is_weaker_alternative and len(new_terms) < 2:
                    continue
            selected_items.append(item)
            covered_terms.update(new_terms)

        return selected_items[:top_k]

    def _extract_chunk_terms(self, item: RetrievedChunk) -> set[str]:
        return extract_terms(f"{item.title_path}\n{item.text}")

    def _load_retrieved_chunks(
        self,
        chunk_ids: list[str],
        scores: list[float],
    ) -> list[RetrievedChunkResponse]:
        chunks = self.chunk_repo.list_by_ids(chunk_ids)
        score_map = {
            chunk_id: score
            for chunk_id, score in zip(chunk_ids, scores)
        }
        payload: list[RetrievedChunkResponse] = []
        for chunk in chunks:
            document = chunk.document
            if document is None:
                continue
            payload.append(
                RetrievedChunkResponse(
                    chunk_id=chunk.id,
                    document_id=document.id,
                    document_title=document.title,
                    title_path=chunk.title_path,
                    snippet=chunk.text[:300],
                    score=round(float(score_map.get(chunk.id, 0.0)), 4),
                )
            )
        return payload
