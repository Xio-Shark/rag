from app.services.chunking import build_chunks


def test_markdown_chunking_preserves_title_path() -> None:
    content = "# 总览\n\n这里是概览。\n\n## 细节\n\n这里是细节。"
    chunks = build_chunks(content=content, file_type="md", chunk_size=50, overlap=10)

    assert len(chunks) >= 2
    assert chunks[0].title_path == "总览"
    assert chunks[1].title_path == "总览 > 细节"
