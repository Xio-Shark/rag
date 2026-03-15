from __future__ import annotations

import argparse
import json

from app.cli.common import managed_session
from app.services.retrieval import ExactRetriever, assess_evidence


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="执行精确检索并查看 top-k 结果")
    parser.add_argument("--query", required=True, help="查询问题")
    parser.add_argument("--limit", type=int, default=5, help="返回条数")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    with managed_session() as session:
        retriever = ExactRetriever(session)
        items = retriever.search(query=args.query, limit=args.limit)
        evidence = assess_evidence(items)
    print(
        json.dumps(
            {
                "confidence": evidence.confidence,
                "refusal_reason": evidence.refusal_reason,
                "items": [
                    {
                        "chunk_id": item.chunk_id,
                        "document_id": item.document_id,
                        "document_title": item.document_title,
                        "title_path": item.title_path,
                        "score": item.score,
                        "snippet": item.text[:180],
                    }
                    for item in items
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
