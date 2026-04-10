from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class EvalSnapshot(BaseModel):
    name: str
    description: str = ""
    top_k: Optional[int] = Field(default=None, ge=1, le=5)
    retrieval_candidate_k: Optional[int] = Field(default=None, ge=1)
    chunk_size: Optional[int] = Field(default=None, ge=50)
    chunk_overlap: Optional[int] = Field(default=None, ge=0)
    retrieval_threshold: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    min_evidence_chunks: Optional[int] = Field(default=None, ge=1)
    prompt_version: Optional[str] = None
    generator_model_name: Optional[str] = None

    def to_settings_update(self) -> dict[str, object]:
        return self.model_dump(exclude_none=True, exclude={"name", "description"})
