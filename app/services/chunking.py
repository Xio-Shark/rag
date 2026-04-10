from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.*)$")


@dataclass
class ChunkDraft:
    sequence: int
    title_path: str
    text: str
    char_count: int
    metadata: dict[str, Any]


def split_markdown_blocks(content: str) -> list[tuple[str, str]]:
    """按标题层级把 Markdown 内容拆成语义块。"""

    headings: list[str] = []
    current_lines: list[str] = []
    current_title_path = ""
    blocks: list[tuple[str, str]] = []

    def flush_block() -> None:
        text = "\n".join(current_lines).strip()
        if text:
            blocks.append((current_title_path, text))
        current_lines.clear()

    for raw_line in content.splitlines():
        line = raw_line.rstrip()
        heading_match = HEADING_PATTERN.match(line)
        if heading_match:
            flush_block()
            level = len(heading_match.group(1))
            title = heading_match.group(2).strip()
            headings[level - 1 :] = [title]
            current_title_path = " > ".join(headings)
            continue
        current_lines.append(line)

    flush_block()
    return blocks or [("", content.strip())]


def split_text_blocks(content: str) -> list[tuple[str, str]]:
    paragraphs = [item.strip() for item in re.split(r"\n\s*\n", content) if item.strip()]
    return [("", paragraph) for paragraph in paragraphs] or [("", content.strip())]


def window_text(
    block_text: str,
    chunk_size: int,
    overlap: int,
) -> list[tuple[str, int, int]]:
    normalized = re.sub(r"\n{3,}", "\n\n", block_text).strip()
    if len(normalized) <= chunk_size:
        return [(normalized, 0, len(normalized))]

    windows: list[tuple[str, int, int]] = []
    start = 0
    step = max(chunk_size - overlap, 1)
    while start < len(normalized):
        end = min(start + chunk_size, len(normalized))
        fragment = normalized[start:end].strip()
        if fragment:
            fragment_start = normalized.find(fragment, start, end)
            if fragment_start < 0:
                fragment_start = start
            fragment_end = fragment_start + len(fragment)
            windows.append((fragment, fragment_start, fragment_end))
        if end >= len(normalized):
            break
        start += step
    return windows


def build_chunks(content: str, file_type: str, chunk_size: int, overlap: int) -> list[ChunkDraft]:
    """把文档内容切成可索引片段。"""

    if file_type == "md":
        blocks = split_markdown_blocks(content)
    else:
        blocks = split_text_blocks(content)

    drafts: list[ChunkDraft] = []
    sequence = 0
    for title_path, block_text in blocks:
        for fragment, start, end in window_text(
            block_text,
            chunk_size=chunk_size,
            overlap=overlap,
        ):
            sequence += 1
            drafts.append(
                ChunkDraft(
                    sequence=sequence,
                    title_path=title_path,
                    text=fragment,
                    char_count=len(fragment),
                    metadata={
                        "heading_path": title_path,
                        "position": {
                            "start": start,
                            "end": end,
                        },
                    },
                )
            )
    return drafts
