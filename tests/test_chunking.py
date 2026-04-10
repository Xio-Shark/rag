from app.services.chunking import build_chunks


def test_markdown_chunking_preserves_title_path() -> None:
    content = "# 总览\n\n这里是概览。\n\n## 细节\n\n这里是细节。"
    chunks = build_chunks(content=content, file_type="md", chunk_size=50, overlap=10)

    assert len(chunks) >= 2
    assert chunks[0].title_path == "总览"
    assert chunks[1].title_path == "总览 > 细节"
    assert chunks[0].metadata["heading_path"] == "总览"
    assert chunks[1].metadata["heading_path"] == "总览 > 细节"


def test_chunk_metadata_contains_position_and_overlap_progress() -> None:
    content = "ABCDEFGHIJ" * 8

    chunks = build_chunks(content=content, file_type="txt", chunk_size=25, overlap=5)

    assert len(chunks) >= 3
    first_position = chunks[0].metadata["position"]
    second_position = chunks[1].metadata["position"]
    assert first_position == {"start": 0, "end": 25}
    assert second_position["start"] < first_position["end"]
    assert second_position["end"] > second_position["start"]
