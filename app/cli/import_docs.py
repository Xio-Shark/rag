from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.cli.common import managed_session
from app.services.ingestion import DocumentIngestionService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="导入 Markdown/TXT 文档并建立索引")
    parser.add_argument("--source-dir", default="data/docs", help="待导入目录")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    with managed_session() as session:
        service = DocumentIngestionService(session)
        result = service.import_directory(source_dir=Path(args.source_dir))
    print(
        json.dumps(
            {
                "imported_count": result.imported_count,
                "skipped_count": result.skipped_count,
                "chunk_count": result.chunk_count,
                "documents": [item.__dict__ for item in result.documents],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
