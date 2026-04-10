from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any, Optional

ROOT_DIR = Path(__file__).resolve().parent.parent

if __package__ in {None, ""}:
    if str(ROOT_DIR) not in sys.path:
        sys.path.insert(0, str(ROOT_DIR))
    from scripts.continuous_task_loop import (
        DEFAULT_CHECK_INTERVAL_MINUTES,
        DEFAULT_MAX_CONSECUTIVE_FAILURES,
        DEFAULT_MAX_ITERATIONS,
        DEFAULT_MAX_SECONDS_PER_ITERATION,
        DEFAULT_STATE_DIR,
        TERMINAL_STATUSES,
        LoopConfig,
        active_iteration_state,
        build_recovery_hints,
        clear_active_iteration,
        clear_loop_process,
        derive_failure_category,
        initialize_runtime_files,
        is_pid_running,
        isoformat_z,
        latest_failure_diagnostics_path,
        load_or_create_state,
        parse_iso_ts,
        parse_next_action_status,
        read_goal_text,
        read_text_if_exists,
        resolve_active_iteration_last_progress_at,
        runtime_paths,
        save_state,
        summarize_iteration_failure,
        summarize_task_queue,
        summarize_transport_error_groups,
        utc_now,
    )
else:
    from .continuous_task_loop import (
        DEFAULT_CHECK_INTERVAL_MINUTES,
        DEFAULT_MAX_CONSECUTIVE_FAILURES,
        DEFAULT_MAX_ITERATIONS,
        DEFAULT_MAX_SECONDS_PER_ITERATION,
        DEFAULT_STATE_DIR,
        TERMINAL_STATUSES,
        LoopConfig,
        active_iteration_state,
        build_recovery_hints,
        clear_active_iteration,
        clear_loop_process,
        derive_failure_category,
        initialize_runtime_files,
        is_pid_running,
        isoformat_z,
        latest_failure_diagnostics_path,
        load_or_create_state,
        parse_iso_ts,
        parse_next_action_status,
        read_goal_text,
        read_text_if_exists,
        resolve_active_iteration_last_progress_at,
        runtime_paths,
        save_state,
        summarize_iteration_failure,
        summarize_task_queue,
        summarize_transport_error_groups,
        utc_now,
    )

DEFAULT_AUTOPILOT_GOAL = (
    "连续推进当前仓库，默认不要停，直到完成队列、达到 10 小时上限或明确验收完成"
)


@dataclass(frozen=True)
class AutopilotConfig:
    goal: str = DEFAULT_AUTOPILOT_GOAL
    state_dir: Path = DEFAULT_STATE_DIR
    duration_hours: float = 10.0
    max_iterations: int = DEFAULT_MAX_ITERATIONS
    max_consecutive_failures: int = DEFAULT_MAX_CONSECUTIVE_FAILURES
    max_seconds_per_iteration: int = DEFAULT_MAX_SECONDS_PER_ITERATION
    check_interval_minutes: float = DEFAULT_CHECK_INTERVAL_MINUTES
    codex_bin: str = "codex"
    model: Optional[str] = None
    sandbox: str = "workspace-write"
    search_enabled: bool = False


@dataclass(frozen=True)
class AutopilotPaths:
    root: Path
    pid_path: Path
    log_path: Path
    meta_path: Path


def autopilot_paths(state_dir: Path) -> AutopilotPaths:
    root = Path(state_dir)
    return AutopilotPaths(
        root=root,
        pid_path=root / "autopilot.pid",
        log_path=root / "autopilot.log",
        meta_path=root / "autopilot.json",
    )


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def read_pid_file(path: Path) -> Optional[int]:
    if not path.exists():
        return None
    try:
        value = path.read_text(encoding="utf-8").strip()
        return int(value) if value else None
    except (OSError, ValueError):
        return None


def remove_if_exists(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        return


def read_json_if_exists(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def to_loop_config(config: AutopilotConfig) -> LoopConfig:
    return LoopConfig(
        goal=config.goal,
        state_dir=config.state_dir,
        duration_hours=config.duration_hours,
        max_iterations=config.max_iterations,
        max_consecutive_failures=config.max_consecutive_failures,
        max_seconds_per_iteration=config.max_seconds_per_iteration,
        codex_bin=config.codex_bin,
        model=config.model,
        sandbox=config.sandbox,
        search_enabled=config.search_enabled,
    )


def resolve_autopilot_goal(explicit_goal: Optional[str], goal_path: Path) -> str:
    if explicit_goal and explicit_goal.strip():
        return explicit_goal.strip()
    existing_goal = read_goal_text(goal_path)
    if existing_goal:
        return existing_goal
    return DEFAULT_AUTOPILOT_GOAL


def build_watchdog_command(config: AutopilotConfig) -> list[str]:
    command = [
        sys.executable,
        str(ROOT_DIR / "scripts" / "continuous_task_loop.py"),
        "--goal",
        config.goal,
        "--state-dir",
        str(config.state_dir),
        "--duration-hours",
        str(config.duration_hours),
        "--max-iterations",
        str(config.max_iterations),
        "--max-consecutive-failures",
        str(config.max_consecutive_failures),
        "--max-seconds-per-iteration",
        str(config.max_seconds_per_iteration),
        "--codex-bin",
        config.codex_bin,
        "--sandbox",
        config.sandbox,
        "--watch",
        "--check-interval-minutes",
        str(config.check_interval_minutes),
    ]
    if config.model:
        command.extend(["--model", config.model])
    if config.search_enabled:
        command.append("--search")
    return command


def refresh_state_for_new_run(state: dict[str, Any], config: AutopilotConfig, now_ts: str) -> None:
    deadline = parse_iso_ts(now_ts) + timedelta(hours=config.duration_hours)
    state["version"] = int(state.get("version", 1) or 1)
    state["goal"] = config.goal
    state["status"] = "running"
    state["started_at"] = now_ts
    state["updated_at"] = now_ts
    state["deadline_at"] = isoformat_z(deadline)
    state["duration_hours"] = config.duration_hours
    state["iteration_count"] = 0
    state["max_iterations"] = config.max_iterations
    state["consecutive_failures"] = 0
    state["max_consecutive_failures"] = config.max_consecutive_failures
    state["max_seconds_per_iteration"] = config.max_seconds_per_iteration
    state["last_thread_id"] = ""
    state["last_stop_reason"] = ""
    state["resume_count"] = 0
    state["last_resume_at"] = ""
    state["last_resume_reason"] = ""
    clear_loop_process(state)
    clear_active_iteration(state)
    state["history"] = []


def should_refresh_run_window(
    state: dict[str, Any],
    config: AutopilotConfig,
    now_ts: str,
) -> bool:
    if state.get("goal") != config.goal:
        return True
    if state.get("status") in TERMINAL_STATUSES:
        return True
    deadline_at = state.get("deadline_at")
    if deadline_at and parse_iso_ts(now_ts) >= parse_iso_ts(str(deadline_at)):
        return True
    if state.get("iteration_count", 0) >= state.get("max_iterations", config.max_iterations):
        return True
    return False


def write_autopilot_metadata(paths: AutopilotPaths, payload: dict[str, Any]) -> None:
    ensure_parent(paths.meta_path)
    paths.meta_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def normalize_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def normalize_transport_error_groups(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    groups: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        count = item.get("count", 0)
        try:
            normalized_count = int(count)
        except (TypeError, ValueError):
            normalized_count = 0
        groups.append(
            {
                "kind": str(item.get("kind", "") or ""),
                "component": str(item.get("component", "") or ""),
                "url": str(item.get("url", "") or ""),
                "http_status": item.get("http_status"),
                "status_reason": str(item.get("status_reason", "") or ""),
                "count": normalized_count,
            }
        )
    return groups


def normalize_transport_errors(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def normalized_latest_failure_diagnostics(diagnostics: dict[str, Any]) -> dict[str, Any]:
    warnings = normalize_string_list(diagnostics.get("warnings"))
    error_messages = normalize_string_list(diagnostics.get("error_messages"))
    transport_errors = normalize_transport_errors(diagnostics.get("transport_errors"))
    try:
        return_code = int(diagnostics.get("return_code") or 0)
    except (TypeError, ValueError):
        return_code = 0

    failure_category = str(diagnostics.get("failure_category", "") or "").strip()
    if not failure_category:
        failure_category = derive_failure_category(
            transport_errors,
            error_messages,
            return_code=return_code,
        )

    transport_error_groups = normalize_transport_error_groups(
        diagnostics.get("transport_error_groups")
    )
    if not transport_error_groups and transport_errors:
        transport_error_groups = summarize_transport_error_groups(transport_errors)

    recovery_hints = normalize_string_list(diagnostics.get("recovery_hints"))
    if not recovery_hints and failure_category:
        recovery_hints = build_recovery_hints(
            failure_category,
            transport_errors,
            warnings,
            error_messages,
        )

    summary = str(diagnostics.get("summary", "") or "").strip()
    if not summary and return_code != 0:
        summary = summarize_iteration_failure(transport_errors, error_messages)

    return {
        "iteration": diagnostics.get("iteration"),
        "attempt": diagnostics.get("attempt"),
        "failure_category": failure_category,
        "summary": summary,
        "transport_error_groups": transport_error_groups,
        "recovery_hints": recovery_hints,
    }


def collect_latest_failure_status(
    loop_paths: Any,
    state: dict[str, Any],
) -> dict[str, Any]:
    diagnostics_path = latest_failure_diagnostics_path(loop_paths, state)
    payload = {
        "latest_failure_iteration": None,
        "latest_failure_diagnostics_path": "",
        "latest_failure_attempt": None,
        "latest_failure_category": "",
        "latest_failure_summary": "",
        "latest_failure_transport_error_groups": [],
        "latest_failure_recovery_hints": [],
    }
    if diagnostics_path is None:
        return payload

    payload["latest_failure_diagnostics_path"] = str(diagnostics_path)
    diagnostics = normalized_latest_failure_diagnostics(read_json_if_exists(diagnostics_path))
    iteration = diagnostics.get("iteration")
    if isinstance(iteration, int):
        payload["latest_failure_iteration"] = iteration
    else:
        try:
            payload["latest_failure_iteration"] = int(diagnostics_path.parent.name)
        except ValueError:
            payload["latest_failure_iteration"] = None
    attempt = diagnostics.get("attempt")
    if isinstance(attempt, int):
        payload["latest_failure_attempt"] = attempt
    else:
        try:
            payload["latest_failure_attempt"] = int(attempt)
        except (TypeError, ValueError):
            payload["latest_failure_attempt"] = None
    payload["latest_failure_category"] = str(diagnostics.get("failure_category", "") or "")
    payload["latest_failure_summary"] = str(diagnostics.get("summary", "") or "")
    transport_error_groups = diagnostics.get("transport_error_groups", [])
    if isinstance(transport_error_groups, list):
        payload["latest_failure_transport_error_groups"] = transport_error_groups
    recovery_hints = diagnostics.get("recovery_hints", [])
    if isinstance(recovery_hints, list):
        payload["latest_failure_recovery_hints"] = recovery_hints
    return payload


def collect_status(state_dir: Path) -> dict[str, Any]:
    loop_paths = runtime_paths(state_dir)
    autopaths = autopilot_paths(state_dir)

    autopilot_pid = read_pid_file(autopaths.pid_path)
    autopilot_running = is_pid_running(autopilot_pid)
    if autopilot_pid is not None and not autopilot_running:
        remove_if_exists(autopaths.pid_path)
        autopilot_pid = None

    state = read_json_if_exists(loop_paths.state_path)
    next_action_text = read_text_if_exists(loop_paths.next_action_path)
    task_queue_text = read_text_if_exists(loop_paths.task_queue_path)
    queue_summary = summarize_task_queue(task_queue_text)
    loop_pid = state.get("loop_pid")
    loop_pid_running = is_pid_running(loop_pid if isinstance(loop_pid, int) else None)
    goal = state.get("goal") or read_goal_text(loop_paths.goal_path) or ""
    metadata = read_json_if_exists(autopaths.meta_path)
    active_state = active_iteration_state(state)
    latest_failure_status = collect_latest_failure_status(loop_paths, state)

    return {
        "state_dir": str(Path(state_dir).resolve()),
        "goal": goal,
        "autopilot_pid": autopilot_pid,
        "autopilot_running": autopilot_running,
        "autopilot_pid_path": str(autopaths.pid_path),
        "autopilot_log_path": str(autopaths.log_path),
        "autopilot_meta_path": str(autopaths.meta_path),
        "loop_status": state.get("status", ""),
        "loop_pid": loop_pid,
        "loop_pid_running": loop_pid_running,
        "started_at": state.get("started_at", ""),
        "updated_at": state.get("updated_at", ""),
        "deadline_at": state.get("deadline_at", ""),
        "duration_hours": state.get("duration_hours"),
        "iteration_count": state.get("iteration_count", 0),
        "max_iterations": state.get("max_iterations", 0),
        "resume_count": state.get("resume_count", 0),
        "last_resume_at": state.get("last_resume_at", ""),
        "last_resume_reason": state.get("last_resume_reason", ""),
        "last_thread_id": state.get("last_thread_id", ""),
        "last_stop_reason": state.get("last_stop_reason", ""),
        "next_action_status": parse_next_action_status(next_action_text),
        "queue_total": queue_summary["total"],
        "queue_completed": queue_summary["completed"],
        "queue_pending": queue_summary["pending"],
        "active_iteration": state.get("active_iteration"),
        "active_iteration_state": active_state,
        "active_iteration_live": active_state == "live",
        "active_iteration_last_progress_at": resolve_active_iteration_last_progress_at(
            loop_paths,
            state,
            include_stale=True,
        ),
        "active_iteration_dir": state.get("active_iteration_dir", ""),
        **latest_failure_status,
        "autopilot_started_at": metadata.get("started_at", ""),
        "autopilot_command": metadata.get("command", []),
        "fresh_run_on_last_start": metadata.get("fresh_run", False),
    }


def emit(payload: dict[str, Any], as_json: bool) -> int:
    if as_json:
        print(json.dumps(payload, ensure_ascii=False))
        return 0

    for key, value in payload.items():
        print(f"{key}: {value}")
    return 0


def terminate_process_group(pid: int, grace_seconds: float = 2.0) -> bool:
    if pid <= 0:
        return False
    try:
        os.killpg(pid, signal.SIGTERM)
    except ProcessLookupError:
        return False
    except OSError:
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            return False

    deadline = time.monotonic() + grace_seconds
    while time.monotonic() < deadline:
        if not is_pid_running(pid):
            return True
        time.sleep(0.05)

    try:
        os.killpg(pid, signal.SIGKILL)
    except ProcessLookupError:
        return True
    except OSError:
        try:
            os.kill(pid, signal.SIGKILL)
        except OSError:
            return not is_pid_running(pid)

    deadline = time.monotonic() + 1.0
    while time.monotonic() < deadline:
        if not is_pid_running(pid):
            return True
        time.sleep(0.05)
    return not is_pid_running(pid)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="后台启动并管理十小时项目自动化任务")
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_shared_runtime_options(target: argparse.ArgumentParser, include_goal: bool) -> None:
        if include_goal:
            target.add_argument("--goal", help="自动化任务总目标；默认复用 GOAL.md 或内置目标")
        target.add_argument(
            "--state-dir",
            default=str(DEFAULT_STATE_DIR),
            help="运行态目录，默认 output/agent-loop",
        )
        target.add_argument("--duration-hours", type=float, default=10.0, help="总运行时长上限")
        target.add_argument("--max-iterations", type=int, default=DEFAULT_MAX_ITERATIONS)
        target.add_argument(
            "--max-consecutive-failures",
            type=int,
            default=DEFAULT_MAX_CONSECUTIVE_FAILURES,
        )
        target.add_argument(
            "--max-seconds-per-iteration",
            type=int,
            default=DEFAULT_MAX_SECONDS_PER_ITERATION,
        )
        target.add_argument(
            "--check-interval-minutes",
            type=float,
            default=DEFAULT_CHECK_INTERVAL_MINUTES,
            help="守护巡检间隔分钟数",
        )
        target.add_argument("--codex-bin", default="codex", help="Codex CLI 可执行文件名")
        target.add_argument("--model", help="指定 Codex 模型")
        target.add_argument(
            "--sandbox",
            default="workspace-write",
            choices=["read-only", "workspace-write", "danger-full-access"],
            help="传递给 codex exec 的 sandbox 模式",
        )
        target.add_argument("--search", action="store_true", help="为 Codex 会话启用网页搜索")
        target.add_argument("--json", action="store_true", help="输出 JSON")

    start_parser = subparsers.add_parser("start", help="后台启动自动化任务")
    add_shared_runtime_options(start_parser, include_goal=True)

    status_parser = subparsers.add_parser("status", help="查看自动化任务状态")
    status_parser.add_argument(
        "--state-dir",
        default=str(DEFAULT_STATE_DIR),
        help="运行态目录，默认 output/agent-loop",
    )
    status_parser.add_argument("--json", action="store_true", help="输出 JSON")

    stop_parser = subparsers.add_parser("stop", help="停止自动化任务和当前 loop")
    stop_parser.add_argument(
        "--state-dir",
        default=str(DEFAULT_STATE_DIR),
        help="运行态目录，默认 output/agent-loop",
    )
    stop_parser.add_argument("--json", action="store_true", help="输出 JSON")

    return parser


def run_start(args: argparse.Namespace) -> int:
    state_dir = Path(args.state_dir)
    loop_paths = runtime_paths(state_dir)
    autopaths = autopilot_paths(state_dir)
    goal = resolve_autopilot_goal(getattr(args, "goal", None), loop_paths.goal_path)
    config = AutopilotConfig(
        goal=goal,
        state_dir=state_dir,
        duration_hours=args.duration_hours,
        max_iterations=args.max_iterations,
        max_consecutive_failures=args.max_consecutive_failures,
        max_seconds_per_iteration=args.max_seconds_per_iteration,
        check_interval_minutes=args.check_interval_minutes,
        codex_bin=args.codex_bin,
        model=args.model,
        sandbox=args.sandbox,
        search_enabled=args.search,
    )

    current_pid = read_pid_file(autopaths.pid_path)
    if current_pid is not None and is_pid_running(current_pid):
        payload = collect_status(state_dir)
        payload["result"] = "already_running"
        return emit(payload, as_json=args.json)

    if current_pid is not None:
        remove_if_exists(autopaths.pid_path)

    loop_config = to_loop_config(config)
    initialize_runtime_files(loop_config, loop_paths)
    state = load_or_create_state(loop_config, loop_paths)
    now_ts = isoformat_z(utc_now())
    fresh_run = should_refresh_run_window(state, config, now_ts)
    if fresh_run:
        refresh_state_for_new_run(state, config, now_ts)
    else:
        state["goal"] = config.goal
        state["updated_at"] = now_ts
    save_state(loop_paths, state)

    command = build_watchdog_command(config)
    ensure_parent(autopaths.log_path)
    with autopaths.log_path.open("a", encoding="utf-8") as log_file:
        log_file.write(f"[{now_ts}] Starting autopilot\n")
        log_file.flush()
        process = subprocess.Popen(
            command,
            cwd=ROOT_DIR,
            stdin=subprocess.DEVNULL,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            text=True,
            start_new_session=True,
        )

    ensure_parent(autopaths.pid_path)
    autopaths.pid_path.write_text(f"{process.pid}\n", encoding="utf-8")
    write_autopilot_metadata(
        autopaths,
        {
            "pid": process.pid,
            "started_at": now_ts,
            "goal": config.goal,
            "command": command,
            "fresh_run": fresh_run,
        },
    )

    payload = collect_status(state_dir)
    payload["result"] = "started"
    payload["fresh_run"] = fresh_run
    return emit(payload, as_json=args.json)


def run_status(args: argparse.Namespace) -> int:
    payload = collect_status(Path(args.state_dir))
    payload["result"] = "status"
    return emit(payload, as_json=args.json)


def run_stop(args: argparse.Namespace) -> int:
    state_dir = Path(args.state_dir)
    loop_paths = runtime_paths(state_dir)
    autopaths = autopilot_paths(state_dir)
    state = read_json_if_exists(loop_paths.state_path)
    stopped_pids: list[int] = []

    autopilot_pid = read_pid_file(autopaths.pid_path)
    loop_pid = state.get("loop_pid")
    unique_pids: list[int] = []
    for pid in [autopilot_pid, loop_pid if isinstance(loop_pid, int) else None]:
        if pid is None or pid in unique_pids:
            continue
        unique_pids.append(pid)

    for pid in unique_pids:
        if is_pid_running(pid):
            terminate_process_group(pid)
            stopped_pids.append(pid)

    remove_if_exists(autopaths.pid_path)

    if state and state.get("status") not in TERMINAL_STATUSES:
        now_ts = isoformat_z(utc_now())
        state["status"] = "interrupted"
        state["updated_at"] = now_ts
        state["last_stop_reason"] = "autopilot_stopped"
        clear_loop_process(state)
        clear_active_iteration(state)
        save_state(loop_paths, state)

    payload = collect_status(state_dir)
    payload["result"] = "stopped"
    payload["stopped_pids"] = stopped_pids
    return emit(payload, as_json=args.json)


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "start":
        return run_start(args)
    if args.command == "status":
        return run_status(args)
    if args.command == "stop":
        return run_stop(args)
    raise SystemExit(f"未知命令: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
