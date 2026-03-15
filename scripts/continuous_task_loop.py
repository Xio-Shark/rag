from __future__ import annotations

import argparse
import codecs
import json
import math
import os
import re
import selectors
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Optional

ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_STATE_DIR = ROOT_DIR / "output" / "agent-loop"
DEFAULT_MAX_ITERATIONS = 40
DEFAULT_MAX_CONSECUTIVE_FAILURES = 3
DEFAULT_MAX_SECONDS_PER_ITERATION = 30 * 60
DEFAULT_CHECK_INTERVAL_MINUTES = 30.0
DEFAULT_PROGRESS_REPORT_MINUTES = 60.0
HTTP_ERROR_RE = re.compile(r"HTTP error:\s+(?P<status>\d+)(?:\s+(?P<reason>[^,]+))?")
URL_IN_MESSAGE_RE = re.compile(r"url:\s+(?P<url>\S+)")
TRANSPORT_ERROR_RE = re.compile(
    r"^\S+\s+(?P<level>ERROR|WARN|INFO)\s+(?P<component>.+?):\s+(?P<message>.+)$"
)
TERMINAL_STATUSES = {
    "completed",
    "blocked",
    "queue_exhausted",
    "deadline_reached",
    "max_iterations_reached",
}
SUCCESS_EXIT_STOP_REASONS = {
    "completed",
    "queue_exhausted",
    "deadline_reached",
    "max_iterations_reached",
}
ITERATION_RESULT_FILENAMES = (
    "events.jsonl",
    "last-message.md",
    "diagnostics.json",
    "stderr.log",
)
ITERATION_WORKSPACE_FILENAMES = ("prompt.md",) + ITERATION_RESULT_FILENAMES
ACTIVE_ITERATION_PROGRESS_FILENAMES = (
    "prompt.md",
    "events.jsonl",
    "stderr.log",
)
RECOVERABLE_STATUSES = {
    "",
    "running",
    "interrupted",
    "too_many_failures",
    "iteration_timeout",
}


@dataclass(frozen=True)
class LoopConfig:
    goal: str
    state_dir: Path = DEFAULT_STATE_DIR
    duration_hours: float = 10.0
    max_iterations: int = DEFAULT_MAX_ITERATIONS
    max_consecutive_failures: int = DEFAULT_MAX_CONSECUTIVE_FAILURES
    max_seconds_per_iteration: int = DEFAULT_MAX_SECONDS_PER_ITERATION
    codex_bin: str = "codex"
    model: Optional[str] = None
    sandbox: str = "workspace-write"
    search_enabled: bool = False
    skip_git_repo_check: bool = True
    dry_run: bool = False


@dataclass(frozen=True)
class RuntimePaths:
    root: Path
    goal_path: Path
    task_queue_path: Path
    next_action_path: Path
    loop_memory_path: Path
    handoff_prompt_path: Path
    watchdog_log_path: Path
    state_path: Path
    iterations_dir: Path


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def isoformat_z(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_iso_ts(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized).astimezone(timezone.utc)


def runtime_paths(state_dir: Path) -> RuntimePaths:
    root = Path(state_dir)
    return RuntimePaths(
        root=root,
        goal_path=root / "GOAL.md",
        task_queue_path=root / "TASK_QUEUE.md",
        next_action_path=root / "NEXT_ACTION.md",
        loop_memory_path=root / "LOOP_MEMORY.md",
        handoff_prompt_path=root / "HANDOFF_PROMPT.md",
        watchdog_log_path=root / "watchdog.log",
        state_path=root / "state.json",
        iterations_dir=root / "iterations",
    )


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def relative_to_root(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT_DIR.resolve()))
    except ValueError:
        return str(path.resolve())


def initialize_runtime_files(config: LoopConfig, paths: RuntimePaths) -> None:
    paths.root.mkdir(parents=True, exist_ok=True)
    paths.iterations_dir.mkdir(parents=True, exist_ok=True)

    if not paths.goal_path.exists():
        paths.goal_path.write_text(
            f"# Goal\n\n{config.goal.strip()}\n",
            encoding="utf-8",
        )

    if not paths.task_queue_path.exists():
        paths.task_queue_path.write_text(
            "\n".join(
                [
                    "# Task Queue",
                    "",
                    "- [ ] 阅读 AGENTS.md、HOOK.md、STANDARDS.md 与运行态文件，确认约束和当前主线",
                    "- [ ] 结合运行态文件，选择一个最小但有价值的增量",
                    "- [ ] 更新 docs/agent-runs/ 任务日志，写清方案对比、测试计划、风险和回滚",
                    "- [ ] 先写/更新匹配测试，再实现增量",
                    "- [ ] 运行匹配验证，并更新 TASK_QUEUE.md、NEXT_ACTION.md、LOOP_MEMORY.md",
                    "",
                ]
            ),
            encoding="utf-8",
        )

    if not paths.next_action_path.exists():
        paths.next_action_path.write_text(
            "\n".join(
                [
                    "# Next Action",
                    "",
                    "Status: continue",
                    "",
                    "本轮首要动作：",
                    "- 先阅读 AGENTS.md、HOOK.md、STANDARDS.md 与 output/agent-loop/ 运行态文件",
                    "- 从 TASK_QUEUE.md 中选择一个最小但有价值的增量",
                    "- 开始实现前先补方案对比、测试计划和任务日志",
                    "- 完成后更新 TASK_QUEUE.md、NEXT_ACTION.md、LOOP_MEMORY.md",
                    "",
                    "交付时至少写清：",
                    "- 本轮已完成",
                    "- 下一轮首要动作",
                    "- 阻塞点（如有）",
                    "",
                ]
            ),
            encoding="utf-8",
        )

    if not paths.loop_memory_path.exists():
        paths.loop_memory_path.write_text(
            "\n".join(
                [
                    "# Loop Memory",
                    "",
                    "本文件用于跨会话保留最小上下文。",
                    "",
                    "当前目标",
                    "",
                    "- <填写当前总目标或主线>",
                    "",
                    "当前主线 / 已完成事项",
                    "",
                    "- <记录最近一轮完成的最小增量>",
                    "- <记录仍在推进的主线>",
                    "",
                    "最近一次验证结果",
                    "",
                    "- <命令>：通过/失败，关键信息>",
                    "",
                    "风险 / 阻塞",
                    "",
                    "- <无则写“当前无代码级阻塞”>",
                    "",
                    "下一步建议",
                    "",
                    "- <给下一轮一个明确的最小动作>",
                    "",
                ]
            ),
            encoding="utf-8",
        )


def default_state(config: LoopConfig, now_ts: str) -> dict[str, Any]:
    now = parse_iso_ts(now_ts)
    deadline = now + timedelta(hours=config.duration_hours)
    return {
        "version": 1,
        "goal": config.goal,
        "status": "running",
        "started_at": now_ts,
        "updated_at": now_ts,
        "deadline_at": isoformat_z(deadline),
        "duration_hours": config.duration_hours,
        "iteration_count": 0,
        "max_iterations": config.max_iterations,
        "consecutive_failures": 0,
        "max_consecutive_failures": config.max_consecutive_failures,
        "max_seconds_per_iteration": config.max_seconds_per_iteration,
        "last_thread_id": "",
        "last_stop_reason": "",
        "loop_pid": None,
        "loop_started_at": "",
        "resume_count": 0,
        "last_resume_at": "",
        "last_resume_reason": "",
        "active_iteration": None,
        "active_iteration_started_at": "",
        "active_iteration_dir": "",
        "active_iteration_attempt": None,
        "active_iteration_last_progress_at": "",
        "active_child_pid": None,
        "iteration_attempts": {},
        "history": [],
    }


def save_state(paths: RuntimePaths, state: dict[str, Any]) -> None:
    ensure_parent(paths.state_path)
    paths.state_path.write_text(
        json.dumps(state, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def load_or_create_state(
    config: LoopConfig,
    paths: RuntimePaths,
    now_ts: Optional[str] = None,
) -> dict[str, Any]:
    if paths.state_path.exists():
        state = json.loads(paths.state_path.read_text(encoding="utf-8"))
        changed = False
        # 兼容旧状态文件，避免新增字段后无法继续之前的运行目录。
        for key, value in {
            "loop_pid": None,
            "loop_started_at": "",
            "resume_count": 0,
            "last_resume_at": "",
            "last_resume_reason": "",
            "active_iteration": None,
            "active_iteration_started_at": "",
            "active_iteration_dir": "",
            "active_iteration_attempt": None,
            "active_iteration_last_progress_at": "",
            "active_child_pid": None,
            "iteration_attempts": {},
            "history": [],
        }.items():
            if key not in state:
                state[key] = value
                changed = True
        for key, value in {
            "goal": config.goal,
            "max_iterations": config.max_iterations,
            "max_consecutive_failures": config.max_consecutive_failures,
            "max_seconds_per_iteration": config.max_seconds_per_iteration,
        }.items():
            if state.get(key) != value:
                state[key] = value
                changed = True
        if changed:
            save_state(paths, state)
        return state

    effective_now = now_ts or isoformat_z(utc_now())
    state = default_state(config, effective_now)
    save_state(paths, state)
    return state


def mark_iteration_started(
    state: dict[str, Any],
    iteration_number: int,
    attempt: int,
    started_at: str,
    iteration_dir: Path,
) -> None:
    state["active_iteration"] = iteration_number
    state["active_iteration_started_at"] = started_at
    state["active_iteration_dir"] = str(iteration_dir)
    state["active_iteration_attempt"] = attempt
    state["active_iteration_last_progress_at"] = ""
    state["active_child_pid"] = None
    state["updated_at"] = started_at
    state["last_stop_reason"] = ""


def clear_active_iteration(state: dict[str, Any]) -> None:
    state["active_iteration"] = None
    state["active_iteration_started_at"] = ""
    state["active_iteration_dir"] = ""
    state["active_iteration_attempt"] = None
    state["active_iteration_last_progress_at"] = ""
    state["active_child_pid"] = None


def mark_active_iteration_progress(state: dict[str, Any], progress_at: str) -> bool:
    if state.get("active_iteration") in {None, ""}:
        return False
    if state.get("active_iteration_last_progress_at") == progress_at:
        return False
    # 输出心跳按秒落盘；同一秒内的重复输出不重复写 state.json，避免长日志时过度刷盘。
    state["active_iteration_last_progress_at"] = progress_at
    state["updated_at"] = progress_at
    return True


def next_iteration_attempt(
    state: dict[str, Any],
    iteration_number: int,
    iteration_dir: Path,
) -> int:
    attempts = dict(state.get("iteration_attempts", {}))
    key = str(iteration_number)
    try:
        previous_attempt = int(attempts.get(key) or 0)
    except (TypeError, ValueError):
        previous_attempt = 0
    # 兼容旧状态：如果状态里还没有该轮尝试次数，但目录已有旧产物，
    # 说明同编号至少尝试过一次，本次应递增到下一次尝试。
    if previous_attempt <= 0 and any(
        (iteration_dir / filename).exists() for filename in ITERATION_WORKSPACE_FILENAMES
    ):
        previous_attempt = 1
    attempt = previous_attempt + 1
    attempts[key] = attempt
    state["iteration_attempts"] = attempts
    return attempt


def mark_loop_process_started(state: dict[str, Any], pid: int, started_at: str) -> None:
    state["loop_pid"] = pid
    state["loop_started_at"] = started_at


def clear_loop_process(state: dict[str, Any]) -> None:
    state["loop_pid"] = None
    state["loop_started_at"] = ""


def is_pid_running(pid: Optional[int]) -> bool:
    if pid is None or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def should_auto_resume(
    state: dict[str, Any],
    next_action_status: str,
    queue_summary: dict[str, int],
    now_ts: str,
    loop_pid_running: bool,
) -> bool:
    if loop_pid_running:
        return False
    if next_action_status in {"completed", "blocked"}:
        return False
    if queue_summary["total"] > 0 and queue_summary["pending"] == 0:
        return False
    if parse_iso_ts(now_ts) >= parse_iso_ts(state["deadline_at"]):
        return False
    return state.get("status", "running") in RECOVERABLE_STATUSES


def derive_resume_reason(state: dict[str, Any]) -> str:
    status = state.get("status", "")
    if status == "interrupted":
        return "resume_after_interrupted"
    if status == "too_many_failures":
        return "resume_after_too_many_failures"
    if status == "iteration_timeout":
        return "resume_after_iteration_timeout"
    if status == "running":
        return "resume_after_process_missing"
    return "resume_after_watchdog_check"


def prepare_state_for_resume(state: dict[str, Any], resume_reason: str, now_ts: str) -> None:
    state["status"] = "running"
    state["consecutive_failures"] = 0
    state["updated_at"] = now_ts
    state["last_stop_reason"] = resume_reason
    state["resume_count"] = int(state.get("resume_count", 0)) + 1
    state["last_resume_at"] = now_ts
    state["last_resume_reason"] = resume_reason
    clear_active_iteration(state)
    clear_loop_process(state)


def summarize_task_queue(text: str) -> dict[str, int]:
    total = 0
    completed = 0
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line.startswith("- [x]") or line.startswith("- [X]"):
            total += 1
            completed += 1
        elif line.startswith("- [ ]"):
            total += 1

    return {
        "total": total,
        "completed": completed,
        "pending": max(total - completed, 0),
    }


def parse_next_action_status(text: str) -> str:
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line.lower().startswith("status:"):
            continue
        status = line.split(":", 1)[1].strip().lower()
        if status in {"continue", "completed", "blocked"}:
            return status
    return "continue"


def format_duration_compact(total_seconds: float) -> str:
    remaining = max(int(total_seconds), 0)
    hours, remainder = divmod(remaining, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours > 0:
        return f"{hours}h{minutes:02d}m"
    if minutes > 0:
        return f"{minutes}m{seconds:02d}s"
    return f"{seconds}s"


def build_watch_progress_report(
    paths: RuntimePaths,
    state: dict[str, Any],
    now_ts: str,
) -> str:
    queue_summary = summarize_task_queue(read_text_if_exists(paths.task_queue_path))
    next_action_status = parse_next_action_status(read_text_if_exists(paths.next_action_path))
    deadline_at = str(state.get("deadline_at", "") or "")
    remaining = "unknown"
    if deadline_at:
        remaining_seconds = (parse_iso_ts(deadline_at) - parse_iso_ts(now_ts)).total_seconds()
        remaining = format_duration_compact(remaining_seconds)

    active_iteration = raw_active_iteration_number(state)
    active_iteration_text = "-" if active_iteration <= 0 else str(active_iteration)
    active_state = active_iteration_state(state)
    active_last_progress = (
        resolve_active_iteration_last_progress_at(paths, state, include_stale=True) or "-"
    )
    last_resume_reason = str(state.get("last_resume_reason", "") or "-")
    updated_at = str(state.get("updated_at", "") or "-")

    return "\n".join(
        [
            f"[{now_ts}] Progress report",
            (
                f"- status={state.get('status', 'running')} "
                f"next_action={next_action_status} "
                f"queue={queue_summary['completed']}/{queue_summary['total']} completed "
                f"pending={queue_summary['pending']}"
            ),
            (
                f"- iterations={state.get('iteration_count', 0)}/{state.get('max_iterations', 0)} "
                f"active_iteration={active_iteration_text} "
                f"active_state={active_state} "
                f"active_last_progress={active_last_progress} "
                f"resume_count={state.get('resume_count', 0)}"
            ),
            (
                f"- deadline_at={deadline_at or '-'} remaining={remaining} "
                f"last_updated={updated_at}"
            ),
            (
                f"- last_resume_reason={last_resume_reason} "
                f"last_thread_id={state.get('last_thread_id', '') or '-'}"
            ),
        ]
    )


def determine_stop_reason(
    state: dict[str, Any],
    next_action_status: str,
    queue_summary: dict[str, int],
    now_ts: str,
) -> Optional[str]:
    now = parse_iso_ts(now_ts)
    deadline = parse_iso_ts(state["deadline_at"])
    if next_action_status == "completed":
        return "completed"
    if next_action_status == "blocked":
        return "blocked"
    if state["consecutive_failures"] >= state["max_consecutive_failures"]:
        return "too_many_failures"
    if state["iteration_count"] >= state["max_iterations"]:
        return "max_iterations_reached"
    if now >= deadline:
        return "deadline_reached"
    if queue_summary["total"] > 0 and queue_summary["pending"] == 0:
        return "queue_exhausted"
    return None


def apply_stop_reason(state: dict[str, Any], stop_reason: str, now_ts: str) -> None:
    state["status"] = stop_reason
    state["updated_at"] = now_ts
    state["last_stop_reason"] = stop_reason
    clear_active_iteration(state)
    clear_loop_process(state)


def resolve_iteration_timeout_seconds(
    state: dict[str, Any],
    configured_timeout_seconds: int,
    now_ts: str,
) -> int:
    remaining_seconds = (parse_iso_ts(state["deadline_at"]) - parse_iso_ts(now_ts)).total_seconds()
    if remaining_seconds <= 0:
        return 0
    return max(1, min(configured_timeout_seconds, math.ceil(remaining_seconds)))


def build_iteration_prompt(
    config: LoopConfig,
    paths: RuntimePaths,
    state: dict[str, Any],
) -> str:
    iteration_number = state["iteration_count"] + 1
    return "\n".join(
        [
            "你是一个新的 Codex 会话。",
            "不要假设你能看到上一轮聊天内容，必须把文件状态当作唯一事实源。",
            "",
            f"当前目标：{config.goal}",
            f"当前迭代：{iteration_number}/{state['max_iterations']}",
            f"截止时间（UTC）：{state['deadline_at']}",
            "",
            "必须先读取并遵守仓库根目录的 AGENTS.md / HOOK.md / STANDARDS.md。",
            "然后读取以下运行态文件：",
            f"- {relative_to_root(paths.goal_path)}",
            f"- {relative_to_root(paths.task_queue_path)}",
            f"- {relative_to_root(paths.next_action_path)}",
            f"- {relative_to_root(paths.loop_memory_path)}",
            f"- {relative_to_root(paths.state_path)}",
            "",
            "执行要求：",
            "1. 选择一个最小但有价值的增量，不要无限扩张范围。",
            "2. 严格遵守仓库流程，必要时更新 docs/agent-runs/。",
            "3. 完成后运行与本轮改动匹配的验证。",
            "4. 在结束前必须更新 TASK_QUEUE.md、NEXT_ACTION.md、LOOP_MEMORY.md。",
            "5. NEXT_ACTION.md 第一处状态行必须使用：Status: continue / completed / blocked。",
            "6. 如果遇到真正阻塞，写清阻塞点和建议接管方式，不要空转。",
            "",
            "你这一轮的目标不是做完全部工作，而是完成一个清晰增量并为下一轮会话做好交接。",
        ]
    )


def build_handoff_prompt(
    config: LoopConfig,
    paths: RuntimePaths,
    state: dict[str, Any],
    last_message: str,
) -> str:
    last_message = last_message.strip() or "上一轮没有捕获到明确的最终消息。"
    prompt_lines = [
        "继续这个仓库的连续任务循环。你是新的 Codex 对话。",
        "不要依赖旧聊天上下文，先读取并遵守 AGENTS.md / HOOK.md / STANDARDS.md。",
        "",
        f"当前总目标：{config.goal}",
        f"当前状态文件：{relative_to_root(paths.state_path)}",
        "请把以下文件当作交接事实源：",
        f"- {relative_to_root(paths.goal_path)}",
        f"- {relative_to_root(paths.task_queue_path)}",
        f"- {relative_to_root(paths.next_action_path)}",
        f"- {relative_to_root(paths.loop_memory_path)}",
        "",
        "上一轮最后消息：",
        last_message,
    ]
    active_iteration = live_active_iteration_number(state)
    raw_active_iteration = raw_active_iteration_number(state)
    if active_iteration > 0:
        active_iteration_dir = paths.iterations_dir / f"{active_iteration:03d}"
        prompt_lines.extend(
            [
                "",
                "若需跟进当前仍在运行的轮次，优先查看：",
                f"- {relative_to_root(active_iteration_dir / 'prompt.md')}",
                f"- {relative_to_root(active_iteration_dir / 'events.jsonl')}",
            ]
        )
        active_iteration_attempt = state.get("active_iteration_attempt")
        active_iteration_last_progress_at = resolve_active_iteration_last_progress_at(paths, state)
        active_child_pid = state.get("active_child_pid")
        active_details: list[str] = []
        if active_iteration_attempt not in {None, ""}:
            active_details.append(f"attempt={active_iteration_attempt}")
        if active_iteration_last_progress_at not in {None, ""}:
            active_details.append(f"last_progress_at={active_iteration_last_progress_at}")
        if active_child_pid not in {None, ""}:
            active_details.append(f"child_pid={active_child_pid}")
        if active_details:
            prompt_lines.append(f"- 运行态元数据：{', '.join(active_details)}")
    elif raw_active_iteration > 0 and active_iteration_state(state) == "stale":
        stale_details = [
            f"iteration={raw_active_iteration}",
            "state=stale",
        ]
        active_iteration_attempt = state.get("active_iteration_attempt")
        active_iteration_last_progress_at = resolve_active_iteration_last_progress_at(
            paths,
            state,
            include_stale=True,
        )
        active_child_pid = state.get("active_child_pid")
        if active_iteration_attempt not in {None, ""}:
            stale_details.append(f"attempt={active_iteration_attempt}")
        if active_iteration_last_progress_at not in {None, ""}:
            stale_details.append(f"last_progress_at={active_iteration_last_progress_at}")
        if active_child_pid not in {None, ""}:
            stale_details.append(f"child_pid={active_child_pid}")
        prompt_lines.extend(
            [
                "",
                "状态文件里仍有一个未收口的活动轮次标记：",
                f"- {', '.join(stale_details)}",
                (
                    "- 该轮次对应的 loop/child pid 已不存活；"
                    "不要把它当成 live child，优先查看失败诊断或等待恢复逻辑接管。"
                ),
            ]
        )
    diagnostics_path = latest_failure_diagnostics_path(paths, state)
    if diagnostics_path is not None:
        prompt_lines.extend(
            [
                "",
                "若需排查上一轮失败，优先查看：",
                f"- {relative_to_root(diagnostics_path)}",
            ]
        )
    prompt_lines.extend(
        [
            "",
            "从 NEXT_ACTION.md 中优先级最高的事项继续，完成一个最小增量后再次更新这些文件。",
        ]
    )
    return "\n".join(prompt_lines)


def build_codex_exec_command(
    config: LoopConfig,
    repo_root: Path,
    last_message_path: Path,
) -> list[str]:
    command = [
        config.codex_bin,
        "exec",
        "--json",
        "--color",
        "never",
        "-C",
        str(repo_root),
        "-s",
        config.sandbox,
        "-o",
        str(last_message_path),
    ]
    if config.skip_git_repo_check:
        command.append("--skip-git-repo-check")
    if config.search_enabled:
        command.append("--search")
    if config.model:
        command.extend(["-m", config.model])
    command.append("-")
    return command


def build_loop_launcher_command(config: LoopConfig) -> list[str]:
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
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
    ]
    if config.model:
        command.extend(["--model", config.model])
    if config.search_enabled:
        command.append("--search")
    return command


def append_history(state: dict[str, Any], item: dict[str, Any], max_items: int = 20) -> None:
    history = list(state.get("history", []))
    history.append(item)
    state["history"] = history[-max_items:]


def parse_jsonl_events(events_text: str) -> list[dict[str, Any]]:
    parsed: list[dict[str, Any]] = []
    for line in events_text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("{"):
            continue
        try:
            parsed.append(json.loads(stripped))
        except json.JSONDecodeError:
            continue
    return parsed


def extract_thread_id(events_text: str) -> str:
    for item in parse_jsonl_events(events_text):
        if item.get("type") == "thread.started":
            return str(item.get("thread_id", ""))
    return ""


def extract_last_agent_message(events_text: str) -> str:
    latest_message = ""
    for item in parse_jsonl_events(events_text):
        completed = item.get("item", {})
        if completed.get("type") == "agent_message" and completed.get("text"):
            latest_message = str(completed["text"])
    return latest_message


def extract_item_error_messages(events_text: str) -> tuple[list[str], list[str]]:
    warnings: list[str] = []
    error_messages: list[str] = []
    for item in parse_jsonl_events(events_text):
        completed = item.get("item", {})
        if completed.get("type") != "error" or not completed.get("message"):
            continue
        message = str(completed["message"]).strip()
        if not message:
            continue
        if "Under-development features enabled" in message:
            warnings.append(message)
            continue
        error_messages.append(message)
    return warnings, error_messages


def classify_transport_error(message: str, http_status: Optional[int]) -> str:
    lowered = message.lower()
    if "websocket" in lowered and http_status is not None:
        return "websocket_http_error"
    if (
        "failed to lookup address information" in lowered
        or "temporary failure in name resolution" in lowered
        or "dns error" in lowered
    ):
        return "dns_lookup_error"
    if "connection refused" in lowered:
        return "connection_refused"
    if "timed out" in lowered or "timeout" in lowered:
        return "transport_timeout"
    return "transport_error"


def extract_transport_errors(events_text: str) -> list[dict[str, Any]]:
    transport_errors: list[dict[str, Any]] = []
    for raw_line in events_text.splitlines():
        stripped = raw_line.strip()
        match = TRANSPORT_ERROR_RE.match(stripped)
        if not match:
            continue
        component = match.group("component").strip()
        if not component.startswith("codex_api::endpoint"):
            continue
        message = match.group("message").strip()
        http_error_match = HTTP_ERROR_RE.search(message)
        url_match = URL_IN_MESSAGE_RE.search(message)
        http_status = None
        status_reason = ""
        if http_error_match:
            http_status = int(http_error_match.group("status"))
            status_reason = (http_error_match.group("reason") or "").strip()
        transport_errors.append(
            {
                "level": match.group("level"),
                "component": component,
                "message": message,
                "kind": classify_transport_error(message, http_status),
                "http_status": http_status,
                "status_reason": status_reason,
                "url": url_match.group("url") if url_match else "",
                "raw_line": stripped,
            }
        )
    return transport_errors


def summarize_iteration_failure(
    transport_errors: list[dict[str, Any]],
    error_messages: list[str],
) -> str:
    if transport_errors:
        primary_error = transport_errors[0]
        component = primary_error["component"]
        url = primary_error.get("url", "")
        if primary_error["kind"] == "websocket_http_error" and primary_error.get("http_status"):
            summary = f"子会话失败：{component} 返回 HTTP {primary_error['http_status']}"
            if primary_error.get("status_reason"):
                summary += f"（{primary_error['status_reason']}）"
            if url:
                summary += f"，目标 {url}"
            return summary + "。"
        if primary_error["kind"] == "dns_lookup_error":
            if url:
                return f"子会话失败：{component} 无法解析地址信息，目标 {url}。"
            return f"子会话失败：{component} 无法解析地址信息。"
        return f"子会话失败：{primary_error['message']}。"

    if error_messages:
        return f"子会话失败：{error_messages[-1]}"

    return "子会话失败，但未捕获到结构化错误摘要。"


def summarize_transport_error_groups(
    transport_errors: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    grouped: dict[tuple[Any, ...], dict[str, Any]] = {}
    for error in transport_errors:
        key = (
            error.get("kind", ""),
            error.get("component", ""),
            error.get("url", ""),
            error.get("http_status"),
            error.get("status_reason", ""),
        )
        if key not in grouped:
            grouped[key] = {
                "kind": error.get("kind", ""),
                "component": error.get("component", ""),
                "url": error.get("url", ""),
                "http_status": error.get("http_status"),
                "status_reason": error.get("status_reason", ""),
                "count": 0,
            }
        grouped[key]["count"] += 1
    return list(grouped.values())


def derive_failure_category(
    transport_errors: list[dict[str, Any]],
    error_messages: list[str],
    *,
    return_code: int,
) -> str:
    if return_code == 0:
        return ""
    if transport_errors:
        kind = str(transport_errors[0].get("kind", "") or "").strip()
        return kind or "transport_error"
    if error_messages:
        lowered = str(error_messages[-1]).lower()
        if "timed out" in lowered or "timeout" in lowered:
            return "child_timeout"
        return "child_error"
    return "unknown_error"


def build_recovery_hints(
    failure_category: str,
    transport_errors: list[dict[str, Any]],
    warnings: list[str],
    error_messages: list[str],
) -> list[str]:
    if not failure_category:
        return []

    primary_error = transport_errors[0] if transport_errors else {}
    url = str(primary_error.get("url", "") or "").strip()
    hints: list[str] = []
    # 提示只给“下一步查什么”，不把现象直接包装成已确认根因。
    if failure_category == "websocket_http_error":
        target_hint = f"（{url}）" if url else ""
        hints.append(
            "检查目标 endpoint / 反向代理是否支持 WebSocket Upgrade"
            f"{target_hint}，确认请求没有被普通 HTTP 转发链路拦截。"
        )
        hints.append(
            "如果当前环境经由企业代理、网关或自建转发层访问 Codex，确认该链路允许 "
            "`Upgrade: websocket` 并保留必要头。"
        )
    elif failure_category == "dns_lookup_error":
        hints.append(
            "检查目标 hostname 的 DNS 解析是否正常，并先核对 Codex 端点 / 代理配置中的域名拼写。"
        )
        hints.append(
            "如果当前环境依赖代理、VPN、hosts 或 split-DNS，"
            "确认这些配置对 `codex exec` 子进程同样生效。"
        )
    elif failure_category == "connection_refused":
        hints.append("检查目标端点是否正在监听，以及本机到该端点的端口连通性是否正常。")
        hints.append("如果前面还有代理或转发层，确认它没有把连接直接拒绝在入口处。")
    elif failure_category == "transport_timeout":
        hints.append("检查当前网络链路是否高延迟或被防火墙拦截，并确认目标端点没有长时间无响应。")
        hints.append("如有代理或网关，确认其超时阈值不会早于 `codex exec` 的会话时限。")
    elif failure_category == "child_timeout":
        hints.append(
            "优先查看 `events.jsonl` 与 `last-message.md`，"
            "确认是任务执行超时而不是网络握手失败。"
        )
    elif failure_category == "child_error":
        hints.append(
            "优先查看 `error_messages`、`events.jsonl` 和 `last-message.md`，"
            "确认是否为子会话自身报错。"
        )
    else:
        hints.append(
            "优先结合 `summary`、`error_messages` 与 `events.jsonl`，"
            "判断失败发生在传输层还是子会话执行阶段。"
        )

    if warnings and any("Under-development features enabled" in warning for warning in warnings):
        hints.append(
            "存在 under-development features warning；"
            "不要把 warning 当成根因，优先按 transport_errors / summary 排查。"
        )
    if (
        not transport_errors
        and error_messages
        and failure_category not in {"child_error", "child_timeout"}
    ):
        hints.append("当前没有提炼出 transport 错误，必要时回看完整 `events.jsonl` 交叉确认。")
    return hints


def build_iteration_diagnostics(
    events_text: str,
    return_code: int,
    thread_id: str,
    iteration_number: Optional[int] = None,
    attempt: Optional[int] = None,
    child_pid: Optional[int] = None,
) -> dict[str, Any]:
    warnings, error_messages = extract_item_error_messages(events_text)
    transport_errors = extract_transport_errors(events_text)
    failure_category = derive_failure_category(
        transport_errors,
        error_messages,
        return_code=return_code,
    )
    return {
        "iteration": iteration_number,
        "attempt": attempt,
        "child_pid": child_pid,
        "thread_id": thread_id,
        "return_code": return_code,
        "warnings": warnings,
        "error_messages": error_messages,
        "failure_category": failure_category,
        "transport_errors": transport_errors,
        "transport_error_groups": summarize_transport_error_groups(transport_errors),
        "recovery_hints": build_recovery_hints(
            failure_category,
            transport_errors,
            warnings,
            error_messages,
        ),
        "summary": summarize_iteration_failure(transport_errors, error_messages)
        if return_code != 0
        else "",
    }


def read_text_if_exists(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def read_goal_text(path: Path) -> str:
    lines = []
    for raw_line in read_text_if_exists(path).splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        lines.append(line)
    return "\n".join(lines).strip()


def latest_recorded_iteration_number(state: dict[str, Any]) -> int:
    history = list(state.get("history", []))
    latest_history_iteration = 0
    if history:
        try:
            latest_history_iteration = int(history[-1].get("iteration") or 0)
        except (TypeError, ValueError):
            latest_history_iteration = 0

    try:
        iteration_count = int(state.get("iteration_count") or 0)
    except (TypeError, ValueError):
        iteration_count = 0

    return max(latest_history_iteration, iteration_count)


def latest_iteration_with_artifacts(paths: RuntimePaths) -> int:
    return latest_iteration_with_artifacts_before(paths)


def latest_iteration_with_artifacts_before(
    paths: RuntimePaths,
    *,
    max_iteration: Optional[int] = None,
) -> int:
    if not paths.iterations_dir.exists():
        return 0

    latest_iteration = 0
    for candidate in paths.iterations_dir.iterdir():
        if not candidate.is_dir():
            continue
        try:
            iteration_number = int(candidate.name)
        except ValueError:
            continue
        if max_iteration is not None and iteration_number > max_iteration:
            continue
        if not any((candidate / filename).exists() for filename in ITERATION_RESULT_FILENAMES):
            continue
        latest_iteration = max(latest_iteration, iteration_number)
    return latest_iteration


def resolve_active_iteration_last_progress_at(
    paths: RuntimePaths,
    state: dict[str, Any],
    *,
    include_stale: bool = False,
) -> str:
    state_value = str(state.get("active_iteration_last_progress_at", "") or "").strip()
    if state_value:
        return state_value

    active_iteration = live_active_iteration_number(state)
    if active_iteration <= 0 and include_stale:
        active_iteration = raw_active_iteration_number(state)
    if active_iteration <= 0:
        return ""

    iteration_dir_value = str(state.get("active_iteration_dir", "") or "").strip()
    if iteration_dir_value:
        iteration_dir = Path(iteration_dir_value)
    else:
        iteration_dir = paths.iterations_dir / f"{active_iteration:03d}"
    if not iteration_dir.exists():
        return ""

    latest_progress_at: Optional[datetime] = None
    # 兼容旧主循环进程：若 state.json 尚未写入心跳，则从活动轮次目录的最新产物推导最近进展时间。
    for filename in ACTIVE_ITERATION_PROGRESS_FILENAMES:
        candidate = iteration_dir / filename
        if not candidate.exists():
            continue
        try:
            candidate_mtime = datetime.fromtimestamp(candidate.stat().st_mtime, tz=timezone.utc)
        except OSError:
            continue
        if latest_progress_at is None or candidate_mtime > latest_progress_at:
            latest_progress_at = candidate_mtime

    if latest_progress_at is None:
        return ""
    return isoformat_z(latest_progress_at)


def raw_active_iteration_number(state: dict[str, Any]) -> int:
    try:
        active_iteration = int(state.get("active_iteration") or 0)
    except (TypeError, ValueError):
        return 0
    return active_iteration if active_iteration > 0 else 0


def live_active_iteration_number(state: dict[str, Any]) -> int:
    active_iteration = raw_active_iteration_number(state)
    if active_iteration <= latest_recorded_iteration_number(state):
        return 0
    active_child_pid = state.get("active_child_pid")
    if active_child_pid not in {None, ""}:
        if not is_pid_running(active_child_pid):
            return 0
        return active_iteration
    if not is_pid_running(state.get("loop_pid")):
        return 0
    return active_iteration


def active_iteration_state(state: dict[str, Any]) -> str:
    if raw_active_iteration_number(state) <= 0:
        return "inactive"
    if live_active_iteration_number(state) > 0:
        return "live"
    return "stale"


def latest_failure_diagnostics_path(paths: RuntimePaths, state: dict[str, Any]) -> Optional[Path]:
    active_iteration = live_active_iteration_number(state)
    latest_on_disk_iteration = latest_iteration_with_artifacts_before(
        paths,
        max_iteration=active_iteration - 1 if active_iteration > 0 else None,
    )
    latest_recorded_iteration = latest_recorded_iteration_number(state)
    if latest_on_disk_iteration > latest_recorded_iteration:
        diagnostics_path = (
            paths.iterations_dir / f"{latest_on_disk_iteration:03d}" / "diagnostics.json"
        )
        if diagnostics_path.exists():
            return diagnostics_path
        return None

    history = list(state.get("history", []))
    if not history:
        return None
    latest_history = history[-1]
    if latest_history.get("return_code") in {0, None}:
        return None
    iteration_number = int(latest_history.get("iteration") or 0)
    if iteration_number <= 0:
        return None
    diagnostics_path = paths.iterations_dir / f"{iteration_number:03d}" / "diagnostics.json"
    if diagnostics_path.exists():
        return diagnostics_path
    return None


def write_handoff_prompt(
    config: LoopConfig,
    paths: RuntimePaths,
    state: dict[str, Any],
    last_message: str,
) -> None:
    paths.handoff_prompt_path.write_text(
        build_handoff_prompt(config, paths, state, last_message),
        encoding="utf-8",
    )


def prepare_iteration_directory(paths: RuntimePaths, iteration_number: int) -> Path:
    iteration_dir = paths.iterations_dir / f"{iteration_number:03d}"
    iteration_dir.mkdir(parents=True, exist_ok=True)
    # 恢复后可能会重试同一轮次，启动前先清理已知产物，避免旧诊断误导新的 handoff。
    for filename in ITERATION_WORKSPACE_FILENAMES:
        candidate = iteration_dir / filename
        if candidate.exists():
            candidate.unlink()
    return iteration_dir


def spawn_detached_loop_process(
    config: LoopConfig,
    paths: RuntimePaths,
    state: dict[str, Any],
    resume_reason: str,
) -> int:
    now_ts = isoformat_z(utc_now())
    prepare_state_for_resume(state, resume_reason=resume_reason, now_ts=now_ts)
    ensure_parent(paths.watchdog_log_path)
    command = build_loop_launcher_command(config)
    with paths.watchdog_log_path.open("a", encoding="utf-8") as log_file:
        log_file.write(f"[{now_ts}] Resuming loop: {resume_reason}\n")
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
    mark_loop_process_started(state, pid=process.pid, started_at=now_ts)
    save_state(paths, state)
    return process.pid


def run_watchdog_check_once(config: LoopConfig, paths: RuntimePaths) -> str:
    state = load_or_create_state(config, paths)
    now_ts = isoformat_z(utc_now())
    next_action_status = parse_next_action_status(read_text_if_exists(paths.next_action_path))
    queue_summary = summarize_task_queue(read_text_if_exists(paths.task_queue_path))
    loop_pid = state.get("loop_pid")
    loop_running = is_pid_running(loop_pid)

    if loop_running:
        print(f"Loop already running with pid {loop_pid}")
        return "already_running"

    state_changed = False
    if loop_pid and not loop_running:
        clear_loop_process(state)
        state["updated_at"] = now_ts
        state_changed = True

    stop_reason = determine_stop_reason(
        state=state,
        next_action_status=next_action_status,
        queue_summary=queue_summary,
        now_ts=now_ts,
    )
    if stop_reason in TERMINAL_STATUSES:
        apply_stop_reason(state, stop_reason, now_ts)
        save_state(paths, state)
        print(f"No resume needed: terminal status={stop_reason}")
        return "no_resume"

    if state_changed:
        save_state(paths, state)

    if not should_auto_resume(
        state=state,
        next_action_status=next_action_status,
        queue_summary=queue_summary,
        now_ts=now_ts,
        loop_pid_running=False,
    ):
        print(
            "No resume needed: "
            f"status={state.get('status', 'running')} "
            f"next_action={next_action_status} "
            f"pending={queue_summary['pending']}"
        )
        return "no_resume"

    resume_reason = derive_resume_reason(state)
    pid = spawn_detached_loop_process(
        config=config,
        paths=paths,
        state=state,
        resume_reason=resume_reason,
    )
    print(f"Resumed loop with pid {pid} ({resume_reason})")
    return "resumed"


def run_watch_mode(
    config: LoopConfig,
    paths: RuntimePaths,
    check_interval_minutes: float,
    progress_report_minutes: float,
) -> int:
    interval_seconds = max(check_interval_minutes * 60.0, 1.0)
    progress_interval_seconds = max(progress_report_minutes * 60.0, 1.0)
    next_progress_report_at = time.monotonic() + progress_interval_seconds
    print(
        "Watchdog started: "
        f"state_dir={relative_to_root(paths.root)} "
        f"interval_minutes={check_interval_minutes:g} "
        f"progress_report_minutes={progress_report_minutes:g}"
    )
    while True:
        action = run_watchdog_check_once(config, paths)
        state = load_or_create_state(config, paths)
        now_monotonic = time.monotonic()
        if now_monotonic >= next_progress_report_at:
            print(build_watch_progress_report(paths, state, now_ts=isoformat_z(utc_now())))
            next_progress_report_at = now_monotonic + progress_interval_seconds
        if action == "no_resume" and state.get("status", "") in TERMINAL_STATUSES:
            print(f"Watchdog exiting: terminal status={state['status']}")
            return 0
        time.sleep(interval_seconds)


def run_command_streaming(
    command: list[str],
    cwd: Path,
    input_text: str,
    output_path: Path,
    timeout_seconds: int,
    on_process_start: Optional[Callable[[int], None]] = None,
    on_output_line: Optional[Callable[[str], None]] = None,
) -> subprocess.CompletedProcess[str]:
    started = time.monotonic()
    captured_chunks: list[str] = []

    with output_path.open("w", encoding="utf-8") as output_file:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=False,
            bufsize=0,
        )
        if on_process_start is not None:
            on_process_start(process.pid)
        assert process.stdin is not None
        assert process.stdout is not None

        process.stdin.write(input_text.encode("utf-8"))
        process.stdin.close()

        def emit_text(text: str) -> None:
            if not text:
                return
            captured_chunks.append(text)
            output_file.write(text)
            output_file.flush()
            sys.stdout.write(text)
            sys.stdout.flush()
            if on_output_line is not None:
                on_output_line(text)

        decoder = codecs.getincrementaldecoder("utf-8")("replace")
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)

            while True:
                elapsed = time.monotonic() - started
                remaining = timeout_seconds - elapsed
                if remaining <= 0:
                    process.kill()
                    process.wait()
                    emit_text(decoder.decode(b"", final=True))
                    raise subprocess.TimeoutExpired(
                        cmd=command,
                        timeout=timeout_seconds,
                        output="".join(captured_chunks),
                        stderr="",
                    )

                events = selector.select(timeout=min(0.5, remaining))
                if not events:
                    if process.poll() is not None:
                        break
                    continue

                for key, _ in events:
                    chunk = os.read(key.fileobj.fileno(), 4096)
                    if not chunk:
                        selector.unregister(key.fileobj)
                        continue
                    emit_text(decoder.decode(chunk))

                if process.poll() is not None and not selector.get_map():
                    break

        emit_text(decoder.decode(b"", final=True))

        return_code = process.wait()

    return subprocess.CompletedProcess(
        args=command,
        returncode=return_code,
        stdout="".join(captured_chunks),
        stderr="",
    )


def run_single_iteration(
    config: LoopConfig,
    paths: RuntimePaths,
    state: dict[str, Any],
) -> tuple[int, Optional[str]]:
    iteration_number = state["iteration_count"] + 1
    iteration_dir = prepare_iteration_directory(paths, iteration_number)
    prompt_path = iteration_dir / "prompt.md"
    events_path = iteration_dir / "events.jsonl"
    diagnostics_path = iteration_dir / "diagnostics.json"
    stderr_path = iteration_dir / "stderr.log"
    last_message_path = iteration_dir / "last-message.md"
    attempt = next_iteration_attempt(
        state,
        iteration_number=iteration_number,
        iteration_dir=iteration_dir,
    )

    prompt = build_iteration_prompt(config, paths, state)
    prompt_path.write_text(prompt + "\n", encoding="utf-8")

    if config.dry_run:
        mark_iteration_started(
            state,
            iteration_number=iteration_number,
            attempt=attempt,
            started_at=isoformat_z(utc_now()),
            iteration_dir=iteration_dir,
        )
        dry_message = "Dry-run: prompt and runtime files prepared, no Codex session started."
        clear_active_iteration(state)
        state["updated_at"] = isoformat_z(utc_now())
        save_state(paths, state)
        last_message_path.write_text(dry_message + "\n", encoding="utf-8")
        write_handoff_prompt(config, paths, state, dry_message)
        print(dry_message)
        print(f"Prompt file: {relative_to_root(prompt_path)}")
        print(f"Handoff file: {relative_to_root(paths.handoff_prompt_path)}")
        return 0, "dry_run"

    if shutil.which(config.codex_bin) is None:
        raise FileNotFoundError(f"未找到 Codex 可执行文件: {config.codex_bin}")

    command = build_codex_exec_command(config, ROOT_DIR, last_message_path)
    started_at = isoformat_z(utc_now())
    timeout_seconds = resolve_iteration_timeout_seconds(
        state=state,
        configured_timeout_seconds=config.max_seconds_per_iteration,
        now_ts=started_at,
    )
    if timeout_seconds <= 0:
        state["updated_at"] = started_at
        state["last_stop_reason"] = "deadline_reached"
        save_state(paths, state)
        write_handoff_prompt(
            config,
            paths,
            state,
            last_message="当前运行窗口已到截止时间，未启动新的子会话。",
        )
        return 0, "deadline_reached"
    # 子会话启动前先落盘当前轮次，便于人工接管时快速定位进行中产物。
    mark_iteration_started(
        state,
        iteration_number=iteration_number,
        attempt=attempt,
        started_at=started_at,
        iteration_dir=iteration_dir,
    )
    save_state(paths, state)
    child_pid: Optional[int] = None

    def handle_child_process_started(pid: int) -> None:
        nonlocal child_pid
        child_pid = pid
        state["active_child_pid"] = pid
        progress_at = isoformat_z(utc_now())
        if mark_active_iteration_progress(state, progress_at):
            save_state(paths, state)
            return
        state["updated_at"] = progress_at
        save_state(paths, state)

    def handle_child_process_output(_line: str) -> None:
        progress_at = isoformat_z(utc_now())
        if mark_active_iteration_progress(state, progress_at):
            save_state(paths, state)

    try:
        stderr_path.write_text(
            "stderr is merged into events.jsonl for live streaming.\n",
            encoding="utf-8",
        )
        result = run_command_streaming(
            command=command,
            cwd=ROOT_DIR,
            input_text=prompt,
            output_path=events_path,
            timeout_seconds=timeout_seconds,
            on_process_start=handle_child_process_started,
            on_output_line=handle_child_process_output,
        )
        finished_at = isoformat_z(utc_now())
    except subprocess.TimeoutExpired as exc:
        finished_at = isoformat_z(utc_now())
        stop_reason = "iteration_timeout"
        exit_code = 1
        if parse_iso_ts(finished_at) >= parse_iso_ts(state["deadline_at"]):
            stop_reason = "deadline_reached"
            exit_code = 0
        events_path.write_text(exc.stdout or "", encoding="utf-8")
        stderr_path.write_text(
            (exc.stderr or "") + "\nTimeout: child session exceeded iteration limit.\n",
            encoding="utf-8",
        )
        state["iteration_count"] += 1
        if stop_reason == "deadline_reached":
            state["consecutive_failures"] = 0
        else:
            state["consecutive_failures"] += 1
        clear_active_iteration(state)
        state["updated_at"] = finished_at
        state["last_thread_id"] = extract_thread_id(exc.stdout or "")
        state["last_stop_reason"] = stop_reason
        append_history(
            state,
            {
                "iteration": iteration_number,
                "started_at": started_at,
                "finished_at": finished_at,
                "thread_id": state["last_thread_id"],
                "attempt": attempt,
                "return_code": None,
                "result": "timeout",
            },
        )
        write_handoff_prompt(
            config,
            paths,
            state,
            last_message=(
                "当前运行窗口达到截止时间，进行中的子会话已被停止。"
                if stop_reason == "deadline_reached"
                else "上一轮因超时终止，请先检查事件日志和 NEXT_ACTION.md。"
            ),
        )
        save_state(paths, state)
        return exit_code, stop_reason

    thread_id = extract_thread_id(result.stdout)
    diagnostics = build_iteration_diagnostics(
        result.stdout,
        return_code=result.returncode,
        thread_id=thread_id,
        iteration_number=iteration_number,
        attempt=attempt,
        child_pid=child_pid,
    )
    if result.returncode != 0:
        diagnostics_path.write_text(
            json.dumps(diagnostics, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    last_message = read_text_if_exists(last_message_path).strip() or extract_last_agent_message(
        result.stdout
    )
    # 子会话失败且没有明确最终消息时，回退到结构化诊断摘要，减少后续人工翻日志成本。
    if result.returncode != 0 and not last_message and diagnostics.get("summary"):
        last_message = str(diagnostics["summary"])

    state["iteration_count"] += 1
    clear_active_iteration(state)
    state["updated_at"] = finished_at
    state["last_thread_id"] = thread_id
    if result.returncode == 0:
        state["consecutive_failures"] = 0
    else:
        state["consecutive_failures"] += 1
    append_history(
        state,
        {
            "iteration": iteration_number,
            "started_at": started_at,
            "finished_at": finished_at,
            "thread_id": thread_id,
            "attempt": attempt,
            "return_code": result.returncode,
            "result": "ok" if result.returncode == 0 else "error",
        },
    )

    queue_summary = summarize_task_queue(read_text_if_exists(paths.task_queue_path))
    next_action_status = parse_next_action_status(read_text_if_exists(paths.next_action_path))
    stop_reason = determine_stop_reason(
        state=state,
        next_action_status=next_action_status,
        queue_summary=queue_summary,
        now_ts=finished_at,
    )
    state["last_stop_reason"] = stop_reason or ""

    write_handoff_prompt(config, paths, state, last_message=last_message)
    save_state(paths, state)

    return result.returncode, stop_reason


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="连续执行 Codex 任务循环，支持跨会话 handoff")
    parser.add_argument("--goal", help="本轮总目标；若未提供则读取已有 GOAL.md")
    parser.add_argument(
        "--state-dir",
        default=str(DEFAULT_STATE_DIR),
        help="运行态文件目录，默认 output/agent-loop",
    )
    parser.add_argument("--duration-hours", type=float, default=10.0, help="总运行时长上限")
    parser.add_argument("--max-iterations", type=int, default=DEFAULT_MAX_ITERATIONS)
    parser.add_argument(
        "--max-consecutive-failures",
        type=int,
        default=DEFAULT_MAX_CONSECUTIVE_FAILURES,
    )
    parser.add_argument(
        "--max-seconds-per-iteration",
        type=int,
        default=DEFAULT_MAX_SECONDS_PER_ITERATION,
    )
    parser.add_argument("--codex-bin", default="codex", help="Codex CLI 可执行文件名")
    parser.add_argument("--model", help="指定 Codex 模型")
    parser.add_argument(
        "--sandbox",
        default="workspace-write",
        choices=["read-only", "workspace-write", "danger-full-access"],
        help="传递给 codex exec 的 sandbox 模式",
    )
    parser.add_argument("--search", action="store_true", help="为 Codex 会话启用网页搜索")
    parser.add_argument(
        "--check-once",
        action="store_true",
        help="执行一次守护巡检；若主循环未运行且任务可恢复，则自动唤醒",
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help="常驻守护模式，按固定间隔重复执行巡检与自动唤醒",
    )
    parser.add_argument(
        "--check-interval-minutes",
        type=float,
        default=DEFAULT_CHECK_INTERVAL_MINUTES,
        help="守护巡检间隔分钟数，默认 30",
    )
    parser.add_argument(
        "--progress-report-minutes",
        type=float,
        default=DEFAULT_PROGRESS_REPORT_MINUTES,
        help="watch 模式下进度摘要输出间隔分钟数，默认 60",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只生成运行态文件和 prompt，不真正启动会话",
    )
    return parser.parse_args()


def resolve_goal(args: argparse.Namespace, paths: RuntimePaths) -> str:
    if args.goal:
        return args.goal.strip()
    if paths.goal_path.exists():
        return read_goal_text(paths.goal_path)
    raise SystemExit("必须通过 --goal 提供目标，或先准备已有的 GOAL.md")


def main() -> int:
    args = parse_args()
    paths = runtime_paths(Path(args.state_dir))
    goal = resolve_goal(args, paths)
    config = LoopConfig(
        goal=goal,
        state_dir=paths.root,
        duration_hours=args.duration_hours,
        max_iterations=args.max_iterations,
        max_consecutive_failures=args.max_consecutive_failures,
        max_seconds_per_iteration=args.max_seconds_per_iteration,
        codex_bin=args.codex_bin,
        model=args.model,
        sandbox=args.sandbox,
        search_enabled=args.search,
        dry_run=args.dry_run,
    )

    initialize_runtime_files(config, paths)
    state = load_or_create_state(config, paths)
    write_handoff_prompt(
        config,
        paths,
        state,
        last_message="初始 handoff 已生成，可用于新会话启动。",
    )

    if args.check_once:
        action = run_watchdog_check_once(config, paths)
        return 0 if action in {"already_running", "resumed", "no_resume"} else 1

    if args.watch:
        return run_watch_mode(
            config,
            paths,
            check_interval_minutes=args.check_interval_minutes,
            progress_report_minutes=args.progress_report_minutes,
        )

    stop_reason = determine_stop_reason(
        state=state,
        next_action_status=parse_next_action_status(read_text_if_exists(paths.next_action_path)),
        queue_summary=summarize_task_queue(read_text_if_exists(paths.task_queue_path)),
        now_ts=isoformat_z(utc_now()),
    )
    if not config.dry_run:
        loop_started_at = isoformat_z(utc_now())
        mark_loop_process_started(state, pid=os.getpid(), started_at=loop_started_at)
        save_state(paths, state)
    if stop_reason and not config.dry_run:
        state["status"] = stop_reason
        state["last_stop_reason"] = stop_reason
        state["updated_at"] = isoformat_z(utc_now())
        clear_loop_process(state)
        save_state(paths, state)
        print(f"Loop stopped before starting: {stop_reason}")
        return 0

    if config.dry_run:
        return run_single_iteration(config, paths, state)[0]

    try:
        while True:
            return_code, stop_reason = run_single_iteration(config, paths, state)
            if return_code != 0 and stop_reason is None:
                print(
                    f"Iteration failed with code {return_code}; "
                    "continuing until stop condition is met."
                )
            if stop_reason:
                state["status"] = stop_reason
                state["updated_at"] = isoformat_z(utc_now())
                clear_loop_process(state)
                save_state(paths, state)
                print(f"Loop stopped: {stop_reason}")
                # 配置上限命中只在当前轮成功时才算成功退出；否则不能掩盖子会话失败。
                if stop_reason in SUCCESS_EXIT_STOP_REASONS and return_code == 0:
                    return 0
                return 1
    except KeyboardInterrupt:
        state["status"] = "interrupted"
        state["updated_at"] = isoformat_z(utc_now())
        state["last_stop_reason"] = "interrupted"
        clear_loop_process(state)
        save_state(paths, state)
        print("\nLoop interrupted by user.")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
