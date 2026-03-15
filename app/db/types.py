from __future__ import annotations

import json
from typing import Any, Optional

from sqlalchemy import JSON
from sqlalchemy.types import TypeDecorator

try:
    from pgvector.sqlalchemy import Vector
except ImportError:  # pragma: no cover - 可选依赖
    Vector = None


def get_embedding_storage_backend(dialect_name: str) -> str:
    if dialect_name == "postgresql" and Vector is not None:
        return "pgvector"
    return "json"


class EmbeddingVector(TypeDecorator):
    """在 PostgreSQL 下使用 pgvector，在其他数据库下回退到 JSON。"""

    impl = JSON
    cache_ok = True
    # 让 ORM 属性在 PostgreSQL + pgvector 场景下暴露距离比较操作。
    if Vector is not None:  # pragma: no branch - 依赖已安装时需要暴露 pgvector 比较器
        comparator_factory = Vector.comparator_factory

    def __init__(self, dimensions: int) -> None:
        super().__init__()
        self.dimensions = dimensions

    def load_dialect_impl(self, dialect):  # type: ignore[override]
        if get_embedding_storage_backend(dialect.name) == "pgvector":
            return dialect.type_descriptor(Vector(self.dimensions))
        return dialect.type_descriptor(JSON())

    def process_bind_param(self, value: Optional[list[float]], dialect) -> Optional[Any]:
        if value is None:
            return None
        if get_embedding_storage_backend(dialect.name) == "pgvector":
            return value
        return json.loads(json.dumps(value))

    def process_result_value(self, value: Optional[Any], dialect) -> Optional[list[float]]:
        if value is None:
            return None
        if isinstance(value, list):
            return [float(item) for item in value]
        return [float(item) for item in value]
