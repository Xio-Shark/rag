from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.exceptions import NotFoundAppError, ValidationAppError
from app.db.models import Chunk, Document
from app.repositories.rag import ChunkRepository, DocumentRepository
from app.schemas.documents import (
    ChunkContextItem,
    ChunkDetailResponse,
    DocumentChunkSummary,
    DocumentDetailResponse,
)
from app.services.chunking import build_chunks
from app.services.embeddings import get_embedding_provider

ALLOWED_SUFFIXES = {".md": "md", ".txt": "txt"}


@dataclass
class ImportedDocument:
    document_id: str
    source_path: str
    status: str
    chunk_count: int


@dataclass
class ImportResult:
    imported_count: int
    skipped_count: int
    chunk_count: int
    documents: list[ImportedDocument]


class DocumentIngestionService:
    def __init__(self, session: Session, settings: Optional[Settings] = None) -> None:
        self.session = session
        self.settings = settings or get_settings()
        self.document_repo = DocumentRepository(session)
        self.chunk_repo = ChunkRepository(session)
        self.embedding_provider = get_embedding_provider()

    def import_directory(self, source_dir: Optional[Path] = None) -> ImportResult:
        directory = Path(source_dir or self.settings.docs_path).resolve()
        if not directory.exists() or not directory.is_dir():
            raise ValidationAppError(f"目录不存在: {directory}")

        imported_count = 0
        skipped_count = 0
        total_chunks = 0
        summaries: list[ImportedDocument] = []

        for file_path in sorted(directory.rglob("*")):
            if not file_path.is_file():
                continue
            if file_path.suffix.lower() not in ALLOWED_SUFFIXES:
                continue
            summary, was_imported = self.import_file(file_path)
            summaries.append(summary)
            total_chunks += summary.chunk_count
            if was_imported:
                imported_count += 1
            else:
                skipped_count += 1

        self.session.commit()
        return ImportResult(
            imported_count=imported_count,
            skipped_count=skipped_count,
            chunk_count=total_chunks,
            documents=summaries,
        )

    def import_file(self, file_path: Path) -> tuple[ImportedDocument, bool]:
        resolved = file_path.resolve()
        self._validate_file(resolved)
        content = resolved.read_text(encoding="utf-8")
        checksum = hashlib.sha256(content.encode("utf-8")).hexdigest()
        existing = self.document_repo.get_by_source_path(str(resolved))

        if existing is not None and existing.checksum == checksum:
            return (
                ImportedDocument(
                    document_id=existing.id,
                    source_path=existing.source_path,
                    status="skipped",
                    chunk_count=existing.chunk_count,
                ),
                False,
            )

        file_type = ALLOWED_SUFFIXES[resolved.suffix.lower()]
        chunk_drafts = build_chunks(
            content=content,
            file_type=file_type,
            chunk_size=self.settings.chunk_size,
            overlap=self.settings.chunk_overlap,
        )
        embeddings = self.embedding_provider.embed_texts([draft.text for draft in chunk_drafts])

        if existing is None:
            document = Document(
                source_path=str(resolved),
                checksum=checksum,
                title=resolved.stem,
                file_type=file_type,
                status="ready",
                chunk_count=len(chunk_drafts),
                content_chars=len(content),
                metadata_json={"source_dir": str(resolved.parent)},
            )
            self.document_repo.add(document)
            self.session.flush()
        else:
            document = existing
            document.checksum = checksum
            document.title = resolved.stem
            document.file_type = file_type
            document.status = "ready"
            document.chunk_count = len(chunk_drafts)
            document.content_chars = len(content)
            document.metadata_json = {"source_dir": str(resolved.parent)}
            self.document_repo.delete_chunks(document.id)
            self.session.flush()

        chunks = [
            Chunk(
                document_id=document.id,
                sequence=draft.sequence,
                title_path=draft.title_path,
                text=draft.text,
                char_count=draft.char_count,
                metadata_json=draft.metadata,
                embedding=embedding,
            )
            for draft, embedding in zip(chunk_drafts, embeddings)
        ]
        self.chunk_repo.add_many(chunks)
        self.session.flush()

        return (
            ImportedDocument(
                document_id=document.id,
                source_path=document.source_path,
                status="imported",
                chunk_count=len(chunks),
            ),
            True,
        )

    def list_documents(self, limit: int = 20) -> list[Document]:
        return self.document_repo.list_recent(limit=limit)

    def get_document_detail(self, document_id: str) -> DocumentDetailResponse:
        document = self.document_repo.get_by_id(document_id)
        if document is None:
            raise NotFoundAppError(f"文档不存在: {document_id}")

        chunks = self.chunk_repo.list_by_document(document_id)
        return DocumentDetailResponse(
            document_id=document.id,
            title=document.title,
            source_path=document.source_path,
            file_type=document.file_type,
            chunk_count=document.chunk_count,
            content_chars=document.content_chars,
            chunks=[
                DocumentChunkSummary(
                    chunk_id=chunk.id,
                    sequence=chunk.sequence,
                    title_path=chunk.title_path,
                    snippet=chunk.text[:260],
                    char_count=chunk.char_count,
                )
                for chunk in chunks
            ],
        )

    def get_chunk_detail(
        self,
        chunk_id: str,
        window: int = 1,
    ) -> ChunkDetailResponse:
        chunk = self.chunk_repo.get_by_id(chunk_id)
        if chunk is None or chunk.document is None:
            raise NotFoundAppError(f"证据片段不存在: {chunk_id}")

        neighbors = self.chunk_repo.list_document_neighbors(
            document_id=chunk.document_id,
            center_sequence=chunk.sequence,
            window=window,
        )
        return ChunkDetailResponse(
            chunk_id=chunk.id,
            document_id=chunk.document_id,
            document_title=chunk.document.title,
            source_path=chunk.document.source_path,
            sequence=chunk.sequence,
            title_path=chunk.title_path,
            text=chunk.text,
            neighbors=[
                ChunkContextItem(
                    chunk_id=item.id,
                    sequence=item.sequence,
                    title_path=item.title_path,
                    snippet=item.text[:260],
                    is_target=item.id == chunk.id,
                )
                for item in neighbors
            ],
        )

    def _validate_file(self, file_path: Path) -> None:
        suffix = file_path.suffix.lower()
        if suffix not in ALLOWED_SUFFIXES:
            raise ValidationAppError(f"不支持的文件类型: {suffix}")
        if file_path.stat().st_size > self.settings.max_file_size_bytes:
            raise ValidationAppError(f"文件过大: {file_path}")
