from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用运行配置。"""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "RAG QA Bench"
    app_env: str = "development"
    app_log_level: str = "INFO"
    database_url: str = "sqlite:///./rag_qa_bench.db"
    docs_dir: Path = Field(default=Path("data/docs"))
    evals_dir: Path = Field(default=Path("data/evals"))
    eval_snapshots_dir: Path = Field(default=Path("data/evals/snapshots"))
    eval_reports_dir: Path = Field(default=Path("output/evals"))
    embedding_model_name: str = "BAAI/bge-small-zh-v1.5"
    embedding_backend: str = "hash"
    embedding_dimensions: int = 64
    generator_model_name: str = "gpt-4.1-mini"
    openai_api_key: str = ""
    openai_api_base_url: str = "https://api.openai.com/v1"
    top_k: int = 3
    retrieval_candidate_k: int = 20
    chunk_size: int = 500
    chunk_overlap: int = 80
    retrieval_threshold: float = 0.15
    min_evidence_chunks: int = 1
    max_file_size_bytes: int = 10 * 1024 * 1024
    prompt_version: str = "v1"
    openai_timeout_seconds: float = 20.0
    openai_max_retries: int = 1
    openai_max_cost_usd: float = 2.0
    feature_evals_enabled: bool = True
    feature_replay_experiments_enabled: bool = True

    @property
    def docs_path(self) -> Path:
        return Path(self.docs_dir).resolve()

    @property
    def evals_path(self) -> Path:
        return Path(self.evals_dir).resolve()

    @property
    def eval_snapshots_path(self) -> Path:
        return Path(self.eval_snapshots_dir).resolve()

    @property
    def eval_reports_path(self) -> Path:
        return Path(self.eval_reports_dir).resolve()

    @property
    def feature_flags(self) -> dict[str, bool]:
        evals_enabled = self.feature_evals_enabled
        return {
            "evals": evals_enabled,
            "replay_experiments": evals_enabled and self.feature_replay_experiments_enabled,
        }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
