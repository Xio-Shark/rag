from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Any

from fastapi import Request

REQUEST_ID_HEADER = "X-Request-ID"
OBSERVABILITY_LOGGER_NAME = "rag.observability"


def configure_logging(log_level: str) -> None:
    level = getattr(logging, log_level.upper(), logging.INFO)
    root_logger = logging.getLogger()

    if not root_logger.handlers:
        logging.basicConfig(level=level, format="%(message)s")

    root_logger.setLevel(level)
    logging.getLogger(OBSERVABILITY_LOGGER_NAME).setLevel(level)


def get_or_create_request_id(request: Request) -> str:
    incoming_request_id = request.headers.get(REQUEST_ID_HEADER, "").strip()
    return incoming_request_id or uuid.uuid4().hex


def get_request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "")


def _normalize_log_fields(fields: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for key, value in fields.items():
        if value is None:
            continue
        if isinstance(value, float):
            normalized[key] = round(value, 3)
            continue
        normalized[key] = value
    return normalized


def build_log_payload(event: str, **fields: Any) -> dict[str, Any]:
    return {"event": event, **_normalize_log_fields(fields)}


def log_event(event: str, **fields: Any) -> None:
    logging.getLogger(OBSERVABILITY_LOGGER_NAME).info(
        json.dumps(build_log_payload(event, **fields), ensure_ascii=False, sort_keys=True)
    )


async def observe_request(request: Request, call_next):
    request_id = get_or_create_request_id(request)
    request.state.request_id = request_id
    started_at = time.perf_counter()

    try:
        response = await call_next(request)
    except Exception as exc:
        log_event(
            "http.request.completed",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            status_code=500,
            duration_ms=(time.perf_counter() - started_at) * 1000,
            error_type=type(exc).__name__,
        )
        raise

    response.headers[REQUEST_ID_HEADER] = request_id
    log_event(
        "http.request.completed",
        request_id=request_id,
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration_ms=(time.perf_counter() - started_at) * 1000,
    )
    return response
