from __future__ import annotations

from typing import Iterable, Optional

from sqlalchemy import delete, desc, select
from sqlalchemy.orm import Session, joinedload

from app.db.models import AnswerRun, Chunk, Document, EvalCase, EvalRun, ReplayExperiment


class DocumentRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_source_path(self, source_path: str) -> Optional[Document]:
        statement = select(Document).where(Document.source_path == source_path)
        return self.session.scalar(statement)

    def get_by_id(self, document_id: str) -> Optional[Document]:
        statement = select(Document).where(Document.id == document_id)
        return self.session.scalar(statement)

    def list_all(self) -> list[Document]:
        statement = select(Document).order_by(Document.source_path.asc())
        return list(self.session.scalars(statement))

    def list_recent(self, limit: int = 20) -> list[Document]:
        statement = select(Document).order_by(desc(Document.created_at)).limit(limit)
        return list(self.session.scalars(statement))

    def count(self) -> int:
        return len(self.list_all())

    def add(self, document: Document) -> Document:
        self.session.add(document)
        return document

    def delete_chunks(self, document_id: str) -> None:
        self.session.execute(delete(Chunk).where(Chunk.document_id == document_id))


class ChunkRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add_many(self, chunks: Iterable[Chunk]) -> None:
        self.session.add_all(list(chunks))

    def get_by_id(self, chunk_id: str) -> Optional[Chunk]:
        statement = (
            select(Chunk)
            .options(joinedload(Chunk.document))
            .where(Chunk.id == chunk_id)
        )
        return self.session.scalar(statement)

    def list_all_with_documents(self) -> list[Chunk]:
        statement = select(Chunk).options(joinedload(Chunk.document)).order_by(Chunk.sequence.asc())
        return list(self.session.scalars(statement))

    def count(self) -> int:
        statement = select(Chunk)
        return len(list(self.session.scalars(statement)))

    def list_by_ids(self, chunk_ids: list[str]) -> list[Chunk]:
        if not chunk_ids:
            return []
        statement = (
            select(Chunk)
            .options(joinedload(Chunk.document))
            .where(Chunk.id.in_(chunk_ids))
        )
        chunks = list(self.session.scalars(statement))
        chunk_map = {chunk.id: chunk for chunk in chunks}
        return [chunk_map[chunk_id] for chunk_id in chunk_ids if chunk_id in chunk_map]

    def list_by_document(self, document_id: str) -> list[Chunk]:
        statement = (
            select(Chunk)
            .options(joinedload(Chunk.document))
            .where(Chunk.document_id == document_id)
            .order_by(Chunk.sequence.asc())
        )
        return list(self.session.scalars(statement))

    def list_document_neighbors(
        self,
        document_id: str,
        center_sequence: int,
        window: int = 1,
    ) -> list[Chunk]:
        statement = (
            select(Chunk)
            .options(joinedload(Chunk.document))
            .where(Chunk.document_id == document_id)
            .where(Chunk.sequence >= max(center_sequence - window, 1))
            .where(Chunk.sequence <= center_sequence + window)
            .order_by(Chunk.sequence.asc())
        )
        return list(self.session.scalars(statement))


class AnswerRunRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, answer_run: AnswerRun) -> AnswerRun:
        self.session.add(answer_run)
        return answer_run

    def get_by_id(self, answer_run_id: str) -> Optional[AnswerRun]:
        statement = select(AnswerRun).where(AnswerRun.id == answer_run_id)
        return self.session.scalar(statement)

    def list_recent(self, limit: int = 20) -> list[AnswerRun]:
        statement = select(AnswerRun).order_by(desc(AnswerRun.created_at)).limit(limit)
        return list(self.session.scalars(statement))


class EvalRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def replace_cases(self, dataset_name: str, cases: list[EvalCase]) -> None:
        self.session.execute(delete(EvalCase).where(EvalCase.dataset_name == dataset_name))
        self.session.add_all(cases)

    def list_cases(self, dataset_name: str) -> list[EvalCase]:
        statement = (
            select(EvalCase)
            .where(EvalCase.dataset_name == dataset_name)
            .order_by(EvalCase.name.asc())
        )
        return list(self.session.scalars(statement))

    def add_run(self, eval_run: EvalRun) -> EvalRun:
        self.session.add(eval_run)
        return eval_run

    def get_latest_run(self) -> Optional[EvalRun]:
        statement = select(EvalRun).order_by(desc(EvalRun.created_at))
        return self.session.scalar(statement)

    def list_runs(self, limit: int = 10) -> list[EvalRun]:
        statement = select(EvalRun).order_by(desc(EvalRun.created_at)).limit(limit)
        return list(self.session.scalars(statement))

    def get_run_by_id(self, eval_run_id: str) -> Optional[EvalRun]:
        statement = select(EvalRun).where(EvalRun.id == eval_run_id)
        return self.session.scalar(statement)


class ReplayExperimentRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, experiment: ReplayExperiment) -> ReplayExperiment:
        self.session.add(experiment)
        return experiment

    def get_by_id(self, experiment_id: str) -> Optional[ReplayExperiment]:
        statement = select(ReplayExperiment).where(ReplayExperiment.id == experiment_id)
        return self.session.scalar(statement)

    def list_recent(
        self,
        limit: int = 20,
        query: Optional[str] = None,
    ) -> list[ReplayExperiment]:
        statement = select(ReplayExperiment)
        if query:
            statement = statement.where(ReplayExperiment.query == query)
        statement = statement.order_by(desc(ReplayExperiment.created_at)).limit(limit)
        return list(self.session.scalars(statement))
