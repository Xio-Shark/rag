from __future__ import annotations

import json
from pathlib import Path

import pytest


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


@pytest.fixture()
def test_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> dict[str, Path]:
    docs_dir = tmp_path / "docs"
    evals_dir = tmp_path / "evals"
    snapshots_dir = evals_dir / "snapshots"
    reports_dir = tmp_path / "reports"
    db_path = tmp_path / "rag_test.db"
    docs_dir.mkdir()
    evals_dir.mkdir()
    snapshots_dir.mkdir()
    reports_dir.mkdir()

    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("DOCS_DIR", str(docs_dir))
    monkeypatch.setenv("EVALS_DIR", str(evals_dir))
    monkeypatch.setenv("EVAL_SNAPSHOTS_DIR", str(snapshots_dir))
    monkeypatch.setenv("EVAL_REPORTS_DIR", str(reports_dir))
    monkeypatch.setenv("EMBEDDING_BACKEND", "hash")
    monkeypatch.setenv("EMBEDDING_DIMENSIONS", "64")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("RETRIEVAL_THRESHOLD", "0.2")
    monkeypatch.setenv("TOP_K", "3")

    from app.core.config import get_settings
    from app.db.session import get_engine, get_session_factory

    get_settings.cache_clear()
    get_engine.cache_clear()
    get_session_factory.cache_clear()

    return {
        "docs_dir": docs_dir,
        "evals_dir": evals_dir,
        "snapshots_dir": snapshots_dir,
        "reports_dir": reports_dir,
    }


@pytest.fixture()
def prepared_environment(test_env: dict[str, Path]) -> dict[str, Path]:
    docs_dir = test_env["docs_dir"]
    evals_dir = test_env["evals_dir"]
    snapshots_dir = test_env["snapshots_dir"]

    file_one = docs_dir / "sample_company_policy.md"
    file_two = docs_dir / "sample_product_notes.txt"
    file_three = docs_dir / "sample_roadmap.md"
    write_text(
        file_one,
        (
            "# 平台核心能力\n\n"
            "系统核心能力包括文档导入、切片索引、检索召回和引用返回。\n\n"
            "## 约束\n\n"
            "当检索不到足够证据时，系统应该拒答，而不是编造答案。\n"
        ),
    )
    write_text(
        file_two,
        (
            "第一版只支持 Markdown 和 TXT 文档。\n\n"
            "评测执行以命令行为主，HTTP 只负责查询结果。\n\n"
            "默认使用精确检索而不是近似索引。\n"
        ),
    )
    write_text(
        file_three,
        (
            "# 版本路线图\n\n"
            "项目按阶段逐步扩展能力。\n\n"
            "## V1.1\n\n"
            "第二阶段补充 PDF 文本提取和基础重排适配，但仍不处理复杂表格抽取。\n\n"
            "## V2\n\n"
            "后续计划扩展多知识库、在线反馈和人工标注后台，支持更完整的质量治理闭环。\n\n"
            "## 取舍原则\n\n"
            "优化顺序固定为引用正确率、groundedness、拒答准确率、检索命中率、延迟。\n"
        ),
    )

    dataset = {
        "dataset_name": "baseline_v1",
        "cases": [
            {
                "name": "平台能力",
                "query": "系统支持哪些核心能力？",
                "should_refuse": False,
                "expected_source_paths": [str(file_one.resolve())],
                "expected_keywords": ["文档导入", "切片索引", "检索召回", "引用返回"],
                "forbidden_terms": ["图像生成"],
            },
            {
                "name": "路线图双事实",
                "query": "路线图如何安排 PDF 和多知识库能力？",
                "should_refuse": False,
                "expected_source_paths": [str(file_three.resolve())],
                "expected_keywords": ["PDF 文本提取", "多知识库"],
                "forbidden_terms": ["复杂表格抽取已在第一版支持"],
            },
            {
                "name": "优化优先级",
                "query": "系统优先优化哪些指标？",
                "should_refuse": False,
                "expected_source_paths": [str(file_three.resolve())],
                "expected_keywords": ["引用正确率", "groundedness", "拒答准确率"],
                "forbidden_terms": ["多轮对话优先"],
            },
            {
                "name": "无依据问题",
                "query": "系统支持图像生成吗？",
                "should_refuse": True,
                "expected_source_paths": [],
                "expected_keywords": [],
                "forbidden_terms": ["已经支持"],
            },
        ],
    }
    (evals_dir / "baseline_v1.json").write_text(
        json.dumps(dataset, ensure_ascii=False), encoding="utf-8"
    )
    (snapshots_dir / "default.json").write_text(
        json.dumps(
            {
                "name": "default",
                "description": "测试默认快照",
                "top_k": 3,
                "retrieval_candidate_k": 20,
                "chunk_size": 500,
                "chunk_overlap": 80,
                "retrieval_threshold": 0.15,
                "min_evidence_chunks": 1,
                "prompt_version": "v1",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (snapshots_dir / "compact_context.json").write_text(
        json.dumps(
            {
                "name": "compact_context",
                "description": "测试压缩上下文快照",
                "top_k": 1,
                "retrieval_candidate_k": 12,
                "chunk_size": 500,
                "chunk_overlap": 80,
                "retrieval_threshold": 0.15,
                "min_evidence_chunks": 1,
                "prompt_version": "v1-compact",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (snapshots_dir / "strict_guard.json").write_text(
        json.dumps(
            {
                "name": "strict_guard",
                "description": "测试保守拒答快照",
                "top_k": 2,
                "retrieval_candidate_k": 20,
                "chunk_size": 500,
                "chunk_overlap": 80,
                "retrieval_threshold": 0.22,
                "min_evidence_chunks": 2,
                "prompt_version": "v1-strict",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return test_env


@pytest.fixture()
def db_session(prepared_environment: dict[str, Path]):
    from app.db.session import get_session_factory, init_database
    from app.services.ingestion import DocumentIngestionService

    init_database()
    session = get_session_factory()()
    service = DocumentIngestionService(session)
    service.import_directory(prepared_environment["docs_dir"])
    session.commit()
    try:
        yield session
    finally:
        session.close()
