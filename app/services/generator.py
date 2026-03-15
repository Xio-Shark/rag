from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Optional

import httpx

from app.core.config import Settings, get_settings
from app.core.exceptions import ExternalServiceAppError
from app.services.retrieval import compute_keyword_overlap


@dataclass
class GenerationResult:
    answer: str
    refusal_reason: Optional[str]
    token_usage: int
    cost: float
    backend: str
    failure_stage: Optional[str] = None


class ExtractiveAnswerGenerator:
    """无外部模型时的可解释回退生成器。"""

    backend_name = "extractive"

    def generate(
        self,
        query: str,
        citations: list[dict[str, Any]],
        settings: Settings,
    ) -> GenerationResult:
        if not citations:
            return GenerationResult(
                answer="",
                refusal_reason="insufficient_grounding",
                token_usage=0,
                cost=0.0,
                backend=self.backend_name,
            )

        strongest = citations[0]
        overlap = compute_keyword_overlap(query, strongest["snippet"], strongest["title_path"])
        if overlap < 0.08:
            return GenerationResult(
                answer="",
                refusal_reason="insufficient_grounding",
                token_usage=0,
                cost=0.0,
                backend=self.backend_name,
            )

        snippets = self._build_snippets(citations=citations, settings=settings)
        answer = "；".join(snippets)
        return GenerationResult(
            answer=answer,
            refusal_reason=None,
            token_usage=0,
            cost=0.0,
            backend=self.backend_name,
        )

    def _build_snippets(
        self,
        citations: list[dict[str, Any]],
        settings: Settings,
    ) -> list[str]:
        snippets: list[str] = []
        seen_title_paths: set[str] = set()
        max_snippets = max(1, min(len(citations), settings.top_k))

        for citation in citations:
            title_path = str(citation.get("title_path", "")).strip()
            if title_path in seen_title_paths:
                continue
            text = str(citation.get("snippet", "")).replace("\n", " ").strip()
            if not text:
                continue
            snippets.append(text[:180])
            if title_path:
                seen_title_paths.add(title_path)
            if len(snippets) >= max_snippets:
                break

        if snippets:
            return snippets

        strongest = citations[0]
        fallback_text = str(strongest.get("snippet", "")).replace("\n", " ").strip()
        return [fallback_text[:180]] if fallback_text else []


class OpenAIAnswerGenerator:
    """调用线上模型生成结构化回答。"""

    backend_name = "openai-chat-completions"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def generate(
        self,
        query: str,
        citations: list[dict[str, Any]],
        settings: Settings,
    ) -> GenerationResult:
        prompt = self._build_prompt(query=query, citations=citations, settings=settings)
        url = f"{settings.openai_api_base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {settings.openai_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": settings.generator_model_name,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "你是一个严格的 RAG 问答助手。"
                        "只能基于给定证据回答。"
                        "如果证据不足，必须返回 refusal_reason，answer 置空。"
                        "输出 JSON，字段仅限 answer 和 refusal_reason。"
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        }
        try:
            response = httpx.post(
                url, headers=headers, json=payload, timeout=settings.openai_timeout_seconds
            )
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise ExternalServiceAppError("生成请求超时") from exc
        except httpx.HTTPError as exc:
            raise ExternalServiceAppError("生成请求失败") from exc

        body = response.json()
        message = body["choices"][0]["message"]["content"]
        try:
            parsed = json.loads(message)
        except json.JSONDecodeError as exc:
            raise ExternalServiceAppError("生成结果不是合法 JSON") from exc

        usage = body.get("usage", {})
        token_usage = int(usage.get("total_tokens", 0) or 0)
        return GenerationResult(
            answer=str(parsed.get("answer", "")).strip(),
            refusal_reason=parsed.get("refusal_reason"),
            token_usage=token_usage,
            cost=0.0,
            backend=self.backend_name,
        )

    def _build_prompt(self, query: str, citations: list[dict[str, Any]], settings: Settings) -> str:
        evidence_lines = []
        for index, citation in enumerate(citations, start=1):
            evidence_lines.append(
                (
                    f"[证据{index}] "
                    f"文档={citation['document_title']} "
                    f"标题路径={citation['title_path']} "
                    f"内容={citation['snippet']}"
                )
            )
        evidence_text = "\n".join(evidence_lines)
        return (
            f"问题：{query}\n"
            f"提示词版本：{settings.prompt_version}\n"
            "请仅根据以下证据回答：\n"
            f"{evidence_text}\n"
            '如果证据不足，请返回 {"answer": "", "refusal_reason": "insufficient_grounding"}。'
        )


def get_answer_generator(settings: Optional[Settings] = None):
    configured = settings or get_settings()
    if configured.openai_api_key:
        return OpenAIAnswerGenerator(configured)
    return ExtractiveAnswerGenerator()


def get_generator_backend_name(settings: Optional[Settings] = None) -> str:
    return get_answer_generator(settings).__class__.backend_name
