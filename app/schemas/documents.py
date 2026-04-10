from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ImportRequest(BaseModel):
    source_dir: Optional[str] = Field(default=None, description="待导入目录，默认为 data/docs")


class ImportedDocumentSummary(BaseModel):
    document_id: str
    source_path: str
    title: str = ""
    status: str
    chunk_count: int
    file_type: str = ""
    content_chars: int = 0
    created_at: Optional[datetime] = None


class ImportResponse(BaseModel):
    imported_count: int
    skipped_count: int
    chunk_count: int
    documents: list[ImportedDocumentSummary]


class DocumentListResponse(BaseModel):
    items: list[ImportedDocumentSummary]


class ChunkContextItem(BaseModel):
    chunk_id: str
    sequence: int
    title_path: str
    snippet: str
    is_target: bool = False


class ChunkDetailResponse(BaseModel):
    chunk_id: str
    document_id: str
    document_title: str
    source_path: str
    sequence: int
    title_path: str
    text: str
    neighbors: list[ChunkContextItem]


class DocumentChunkSummary(BaseModel):
    chunk_id: str
    sequence: int
    title_path: str
    snippet: str
    char_count: int


class DocumentDetailResponse(BaseModel):
    document_id: str
    title: str
    source_path: str
    file_type: str
    chunk_count: int
    content_chars: int
    chunks: list[DocumentChunkSummary]
