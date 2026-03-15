from __future__ import annotations

import json
import logging
import time
import uuid
from threading import Lock
from typing import Any

from fastapi import Request

REQUEST_ID_HEADER = "X-Request-ID"
OBSERVABILITY_LOGGER_NAME = "rag.observability"
METRICS_CONTENT_TYPE = "text/plain; version=0.0.4; charset=utf-8"

_request_metrics_lock = Lock()
_request_metrics: dict[tuple[str, str, str], dict[str, float]] = {}


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


def _record_request_metric(
    method: str,
    path: str,
    status_code: int,
    duration_ms: float,
) -> None:
    metric_key = (method.upper(), path, str(status_code))
    with _request_metrics_lock:
        snapshot = _request_metrics.setdefault(metric_key, {"count": 0.0, "duration_ms_sum": 0.0})
        snapshot["count"] += 1.0
        snapshot["duration_ms_sum"] += duration_ms


def _format_metric_labels(method: str, path: str, status_code: str) -> str:
    def escape(value: str) -> str:
        return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")

    return (
        f'method="{escape(method)}",'
        f'path="{escape(path)}",'
        f'status_code="{escape(status_code)}"'
    )


def render_metrics() -> str:
    lines = [
        "# HELP rag_http_requests_total Total completed HTTP requests.",
        "# TYPE rag_http_requests_total counter",
        "# HELP rag_http_request_duration_ms_count Total completed HTTP request observations.",
        "# TYPE rag_http_request_duration_ms_count counter",
        (
            "# HELP rag_http_request_duration_ms_sum "
            "Total completed HTTP request duration in milliseconds."
        ),
        "# TYPE rag_http_request_duration_ms_sum counter",
    ]

    with _request_metrics_lock:
        items = sorted(_request_metrics.items())

    for (method, path, status_code), values in items:
        labels = _format_metric_labels(method, path, status_code)
        count = int(values["count"])
        duration_ms_sum = round(values["duration_ms_sum"], 3)
        lines.append(f"rag_http_requests_total{{{labels}}} {count}")
        lines.append(f"rag_http_request_duration_ms_count{{{labels}}} {count}")
        lines.append(f"rag_http_request_duration_ms_sum{{{labels}}} {duration_ms_sum}")

    return "\n".join(lines) + "\n"


def reset_metrics() -> None:
    with _request_metrics_lock:
        _request_metrics.clear()


async def observe_request(request: Request, call_next):
    request_id = get_or_create_request_id(request)
    request.state.request_id = request_id
    started_at = time.perf_counter()

    try:
        response = await call_next(request)
    except Exception as exc:
        duration_ms = (time.perf_counter() - started_at) * 1000
        _record_request_metric(request.method, request.url.path, 500, duration_ms)
        log_event(
            "http.request.completed",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            status_code=500,
            duration_ms=duration_ms,
            error_type=type(exc).__name__,
        )
        raise

    response.headers[REQUEST_ID_HEADER] = request_id
    duration_ms = (time.perf_counter() - started_at) * 1000
    _record_request_metric(request.method, request.url.path, response.status_code, duration_ms)
    log_event(
        "http.request.completed",
        request_id=request_id,
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration_ms=duration_ms,
    )
    return response
