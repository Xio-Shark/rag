from __future__ import annotations

import hashlib
import math
import re
from functools import lru_cache
from typing import Optional

from app.core.config import Settings, get_settings

TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]+")


def normalize_vector(values: list[float]) -> list[float]:
    norm = math.sqrt(sum(item * item for item in values))
    if norm == 0:
        return values
    return [item / norm for item in values]


class HashEmbeddingProvider:
    """轻量级可复现嵌入，便于本地开发和测试。"""

    def __init__(self, dimensions: int) -> None:
        self.dimensions = dimensions
        self.backend_name = "hash"

    def _tokenize(self, text: str) -> list[str]:
        tokens = TOKEN_PATTERN.findall(text.lower())
        expanded: list[str] = []
        for token in tokens:
            if re.match(r"^[\u4e00-\u9fff]+$", token):
                if len(token) == 1:
                    expanded.append(token)
                else:
                    expanded.extend(token[index : index + 2] for index in range(len(token) - 1))
            else:
                expanded.append(token)
        return expanded

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            vector = [0.0 for _ in range(self.dimensions)]
            for token in self._tokenize(text):
                digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
                bucket = int(digest, 16) % self.dimensions
                vector[bucket] += 1.0
            vectors.append(normalize_vector(vector))
        return vectors


class SentenceTransformerEmbeddingProvider:
    """本地模型嵌入。"""

    def __init__(self, model_name: str) -> None:
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer(model_name)
        self.backend_name = "sentence-transformers"

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        embeddings = self.model.encode(texts, normalize_embeddings=True)
        return [list(map(float, item)) for item in embeddings.tolist()]


@lru_cache(maxsize=1)
def get_embedding_provider() -> object:
    settings = get_settings()
    if settings.embedding_backend == "sentence-transformers":
        return SentenceTransformerEmbeddingProvider(settings.embedding_model_name)
    if settings.embedding_backend == "hash":
        return HashEmbeddingProvider(settings.embedding_dimensions)
    try:
        return SentenceTransformerEmbeddingProvider(settings.embedding_model_name)
    except Exception:
        return HashEmbeddingProvider(settings.embedding_dimensions)


def get_embedding_backend_name(settings: Optional[Settings] = None) -> str:
    configured = settings or get_settings()
    if configured.embedding_backend == "hash":
        return "hash"
    provider = get_embedding_provider()
    return getattr(provider, "backend_name", "hash")
