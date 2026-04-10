from app.services.retrieval import ExactRetriever, assess_evidence


def test_exact_retrieval_returns_relevant_chunk(db_session) -> None:
    retriever = ExactRetriever(db_session)
    results = retriever.search("系统支持哪些核心能力", limit=3)
    evidence = assess_evidence(results)

    assert results
    assert any("文档导入" in item.text for item in results)
    assert evidence.refusal_reason is None
    assert evidence.confidence > 0


def test_exact_retrieval_falls_back_to_application_scoring_when_postgres_uses_json(
    db_session,
    monkeypatch,
) -> None:
    retriever = ExactRetriever(db_session)
    real_bind = retriever.session.get_bind()

    class FakeDialect:
        name = "postgresql"

    class FakeBind:
        dialect = FakeDialect()

    def fake_get_bind(*args, **kwargs):
        if args or kwargs:
            return real_bind
        return FakeBind()

    monkeypatch.setattr(retriever.session, "get_bind", fake_get_bind)
    monkeypatch.setattr("app.services.retrieval.get_embedding_storage_backend", lambda _: "json")

    results = retriever.search("系统支持哪些核心能力", limit=3)

    assert results
    assert any("文档导入" in item.text for item in results)


def test_exact_retrieval_falls_back_when_pgvector_distance_expression_is_unavailable(
    db_session,
    monkeypatch,
) -> None:
    retriever = ExactRetriever(db_session)
    real_bind = retriever.session.get_bind()

    class FakeDialect:
        name = "postgresql"

    class FakeBind:
        dialect = FakeDialect()

    def fake_get_bind(*args, **kwargs):
        if args or kwargs:
            return real_bind
        return FakeBind()

    monkeypatch.setattr(retriever.session, "get_bind", fake_get_bind)
    monkeypatch.setattr(
        "app.services.retrieval.get_embedding_storage_backend",
        lambda _: "pgvector",
    )
    monkeypatch.setattr("app.services.retrieval.build_pgvector_distance_expression", lambda _: None)

    results = retriever.search("系统支持哪些核心能力", limit=3)

    assert results
    assert any("文档导入" in item.text for item in results)
