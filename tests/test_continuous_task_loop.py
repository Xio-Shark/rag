from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

from scripts.continuous_task_loop import (
    LoopConfig,
    build_codex_exec_command,
    build_handoff_prompt,
    build_iteration_diagnostics,
    build_iteration_prompt,
    build_loop_launcher_command,
    build_watch_progress_report,
    clear_active_iteration,
    clear_loop_process,
    default_state,
    determine_stop_reason,
    initialize_runtime_files,
    is_pid_running,
    live_active_iteration_number,
    load_or_create_state,
    mark_iteration_started,
    mark_loop_process_started,
    next_iteration_attempt,
    parse_next_action_status,
    prepare_iteration_directory,
    prepare_state_for_resume,
    read_goal_text,
    resolve_iteration_timeout_seconds,
    run_command_streaming,
    run_watchdog_check_once,
    runtime_paths,
    save_state,
    should_auto_resume,
    summarize_task_queue,
)

ROOT_DIR = Path(__file__).resolve().parents[1]


def write_fake_codex_bin(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "#!/usr/bin/env python3",
                "from __future__ import annotations",
                "",
                "import json",
                "import sys",
                "import time",
                "from pathlib import Path",
                "",
                "args = sys.argv[1:]",
                'if args and args[0] == "exec":',
                "    args = args[1:]",
                "",
                "output_path = None",
                "index = 0",
                "while index < len(args):",
                '    if args[index] == "-o" and index + 1 < len(args):',
                "        output_path = Path(args[index + 1])",
                "        index += 2",
                "        continue",
                "    index += 1",
                "",
                "prompt = sys.stdin.read()",
                "if not prompt.strip():",
                "    raise SystemExit(2)",
                "",
                "if output_path is not None:",
                '    output_path.write_text(',
                '        "Fake child completed verification.\\n",',
                '        encoding="utf-8",',
                "    )",
                "",
                'print(',
                '    json.dumps({"type": "thread.started", "thread_id": "fake-thread-001"}),',
                "    flush=True,",
                ")",
                "time.sleep(1.0)",
                'print(',
                '    json.dumps(',
                '        {',
                '            "type": "item.completed",',
                '            "item": {',
                '                "type": "agent_message",',
                '                "text": "Fake child completed verification.",',
                "            },",
                "        }",
                "    ),",
                "    flush=True,",
                ")",
                "time.sleep(0.1)",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    path.chmod(0o755)


def write_failing_fake_codex_bin(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "#!/usr/bin/env python3",
                "from __future__ import annotations",
                "",
                "import json",
                "import sys",
                "import time",
                "from pathlib import Path",
                "",
                "args = sys.argv[1:]",
                'if args and args[0] == "exec":',
                "    args = args[1:]",
                "",
                "output_path = None",
                "index = 0",
                "while index < len(args):",
                '    if args[index] == "-o" and index + 1 < len(args):',
                "        output_path = Path(args[index + 1])",
                "        index += 2",
                "        continue",
                "    index += 1",
                "",
                "prompt = sys.stdin.read()",
                "if not prompt.strip():",
                "    raise SystemExit(2)",
                "",
                "if output_path is not None:",
                '    output_path.write_text("", encoding="utf-8")',
                "",
                'print(',
                '    json.dumps({"type": "thread.started", "thread_id": "fake-thread-err-001"}),',
                "    flush=True,",
                ")",
                "time.sleep(0.2)",
                'print('
                '    "2026-03-15T02:00:00.000000Z ERROR codex_api::endpoint::responses_websocket: '
                'failed to connect to websocket: HTTP error: 426 Upgrade Required, '
                'url: wss://aixj.vip/responses",'
                "    flush=True,",
                ")",
                "time.sleep(0.1)",
                'print(',
                '    json.dumps(',
                '        {',
                '            "type": "item.completed",',
                '            "item": {',
                '                "type": "error",',
                '                "message": "Fake child failed verification.",',
                "            },",
                "        }",
                "    ),",
                "    flush=True,",
                ")",
                "time.sleep(0.1)",
                "raise SystemExit(1)",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    path.chmod(0o755)


def write_partial_output_child(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "#!/usr/bin/env python3",
                "from __future__ import annotations",
                "",
                "import sys",
                "import time",
                "",
                "sys.stdin.read()",
                "sys.stdout.write('partial output without newline')",
                "sys.stdout.flush()",
                "time.sleep(2.0)",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    path.chmod(0o755)


def test_build_iteration_diagnostics_extracts_transport_errors_and_summary() -> None:
    events_text = "\n".join(
        [
            '{"type":"thread.started","thread_id":"fake-thread-err-001"}',
            (
                '{"type":"item.completed","item":{"type":"error","message":"'
                'Under-development features enabled: responses_websockets_v2."}}'
            ),
            "2026-03-15T02:00:00.000000Z ERROR codex_api::endpoint::responses_websocket: "
            "failed to connect to websocket: HTTP error: 426 Upgrade Required, "
            "url: wss://aixj.vip/responses",
        ]
    )

    diagnostics = build_iteration_diagnostics(
        events_text,
        return_code=1,
        thread_id="fake-thread-err-001",
    )

    assert diagnostics["return_code"] == 1
    assert diagnostics["thread_id"] == "fake-thread-err-001"
    assert diagnostics["warnings"] == [
        "Under-development features enabled: responses_websockets_v2."
    ]
    assert diagnostics["error_messages"] == []
    assert diagnostics["failure_category"] == "websocket_http_error"
    assert diagnostics["transport_errors"][0]["kind"] == "websocket_http_error"
    assert (
        diagnostics["transport_errors"][0]["component"]
        == "codex_api::endpoint::responses_websocket"
    )
    assert diagnostics["transport_errors"][0]["http_status"] == 426
    assert diagnostics["transport_errors"][0]["url"] == "wss://aixj.vip/responses"
    assert diagnostics["transport_error_groups"][0]["kind"] == "websocket_http_error"
    assert diagnostics["transport_error_groups"][0]["count"] == 1
    assert any("WebSocket Upgrade" in hint for hint in diagnostics["recovery_hints"])
    assert any("不要把 warning 当成根因" in hint for hint in diagnostics["recovery_hints"])
    assert "HTTP 426" in diagnostics["summary"]
    assert "wss://aixj.vip/responses" in diagnostics["summary"]


def test_build_iteration_diagnostics_groups_repeated_dns_errors_and_adds_hints() -> None:
    events_text = "\n".join(
        [
            '{"type":"thread.started","thread_id":"fake-thread-dns-001"}',
            (
                '{"type":"item.completed","item":{"type":"error","message":"'
                "Falling back from WebSockets to HTTPS transport. "
                "stream disconnected before completion: failed to lookup address "
                'information: nodename nor servname provided, or not known"}}'
            ),
            "2026-03-15T02:00:00.000000Z ERROR codex_api::endpoint::responses_websocket: "
            "failed to connect to websocket: IO error: failed to lookup address information: "
            "nodename nor servname provided, or not known, url: wss://aixj.vip/responses",
            "2026-03-15T02:00:01.000000Z ERROR codex_api::endpoint::responses_websocket: "
            "failed to connect to websocket: IO error: failed to lookup address information: "
            "nodename nor servname provided, or not known, url: wss://aixj.vip/responses",
        ]
    )

    diagnostics = build_iteration_diagnostics(
        events_text,
        return_code=1,
        thread_id="fake-thread-dns-001",
    )

    assert diagnostics["failure_category"] == "dns_lookup_error"
    assert diagnostics["transport_error_groups"] == [
        {
            "kind": "dns_lookup_error",
            "component": "codex_api::endpoint::responses_websocket",
            "url": "wss://aixj.vip/responses",
            "http_status": None,
            "status_reason": "",
            "count": 2,
        }
    ]
    assert any("DNS" in hint for hint in diagnostics["recovery_hints"])
    assert any("代理" in hint for hint in diagnostics["recovery_hints"])
    assert "无法解析地址信息" in diagnostics["summary"]


def test_initialize_runtime_files_creates_expected_templates(tmp_path: Path) -> None:
    config = LoopConfig(goal="持续推进仓库任务", state_dir=tmp_path)
    paths = runtime_paths(config.state_dir)

    initialize_runtime_files(config, paths)

    task_queue = paths.task_queue_path.read_text(encoding="utf-8")
    next_action = paths.next_action_path.read_text(encoding="utf-8")
    loop_memory = paths.loop_memory_path.read_text(encoding="utf-8")

    assert paths.root.exists()
    assert paths.iterations_dir.exists()
    assert "持续推进仓库任务" in paths.goal_path.read_text(encoding="utf-8")
    assert "Status: continue" in next_action
    assert "更新 docs/agent-runs/ 任务日志" in task_queue
    assert "先写/更新匹配测试，再实现增量" in task_queue
    assert "开始实现前先补方案对比、测试计划和任务日志" in next_action
    assert "交付时至少写清" in next_action
    assert "当前主线 / 已完成事项" in loop_memory
    assert "最近一次验证结果" in loop_memory
    assert "风险 / 阻塞" in loop_memory


def test_load_or_create_state_initializes_deadline_and_counts(tmp_path: Path) -> None:
    config = LoopConfig(goal="连续执行", state_dir=tmp_path, duration_hours=10.0)
    paths = runtime_paths(config.state_dir)
    initialize_runtime_files(config, paths)

    state = load_or_create_state(config, paths, now_ts="2026-03-15T01:00:00Z")

    assert state["goal"] == "连续执行"
    assert state["status"] == "running"
    assert state["iteration_count"] == 0
    assert state["consecutive_failures"] == 0
    assert state["deadline_at"] == "2026-03-15T11:00:00Z"
    assert state["active_iteration"] is None
    assert state["active_iteration_started_at"] == ""
    assert state["active_iteration_dir"] == ""
    assert state["active_iteration_attempt"] is None
    assert state["active_iteration_last_progress_at"] == ""
    assert state["active_child_pid"] is None
    assert state["loop_pid"] is None
    assert state["loop_started_at"] == ""
    assert state["iteration_attempts"] == {}
    assert state["resume_count"] == 0
    assert state["last_resume_at"] == ""
    assert state["last_resume_reason"] == ""
    saved_state = json.loads(paths.state_path.read_text(encoding="utf-8"))
    assert saved_state["deadline_at"] == "2026-03-15T11:00:00Z"


def test_load_or_create_state_backfills_active_iteration_fields(tmp_path: Path) -> None:
    config = LoopConfig(goal="连续执行", state_dir=tmp_path)
    paths = runtime_paths(config.state_dir)
    initialize_runtime_files(config, paths)
    paths.state_path.write_text(
        json.dumps(
            {
                "version": 1,
                "goal": config.goal,
                "status": "running",
                "started_at": "2026-03-15T01:00:00Z",
                "updated_at": "2026-03-15T01:00:00Z",
                "deadline_at": "2026-03-15T11:00:00Z",
                "duration_hours": 10.0,
                "iteration_count": 0,
                "max_iterations": 40,
                "consecutive_failures": 0,
                "max_consecutive_failures": 3,
                "max_seconds_per_iteration": 1800,
                "last_thread_id": "",
                "last_stop_reason": "",
                "history": [],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    state = load_or_create_state(config, paths)

    assert state["active_iteration"] is None
    assert state["active_iteration_started_at"] == ""
    assert state["active_iteration_dir"] == ""
    assert state["active_iteration_attempt"] is None
    assert state["active_iteration_last_progress_at"] == ""
    assert state["active_child_pid"] is None
    assert state["loop_pid"] is None
    assert state["loop_started_at"] == ""
    assert state["iteration_attempts"] == {}
    assert state["resume_count"] == 0
    assert state["last_resume_at"] == ""
    assert state["last_resume_reason"] == ""
    saved_state = json.loads(paths.state_path.read_text(encoding="utf-8"))
    assert saved_state["active_iteration"] is None
    assert saved_state["active_iteration_attempt"] is None
    assert saved_state["active_iteration_last_progress_at"] == ""
    assert saved_state["active_child_pid"] is None
    assert saved_state["iteration_attempts"] == {}


def test_mark_iteration_started_and_clear_active_iteration() -> None:
    state = default_state(
        LoopConfig(goal="连续执行"),
        now_ts="2026-03-15T01:00:00Z",
    )

    mark_iteration_started(
        state,
        iteration_number=1,
        attempt=2,
        started_at="2026-03-15T01:05:00Z",
        iteration_dir=Path("/tmp/agent-loop/iterations/001"),
    )

    assert state["active_iteration"] == 1
    assert state["active_iteration_started_at"] == "2026-03-15T01:05:00Z"
    assert state["active_iteration_dir"] == "/tmp/agent-loop/iterations/001"
    assert state["active_iteration_attempt"] == 2
    assert state["active_iteration_last_progress_at"] == ""
    assert state["active_child_pid"] is None

    clear_active_iteration(state)

    assert state["active_iteration"] is None
    assert state["active_iteration_started_at"] == ""
    assert state["active_iteration_dir"] == ""
    assert state["active_iteration_attempt"] is None
    assert state["active_iteration_last_progress_at"] == ""
    assert state["active_child_pid"] is None


def test_next_iteration_attempt_tracks_retry_sequence(tmp_path: Path) -> None:
    state = default_state(
        LoopConfig(goal="连续执行"),
        now_ts="2026-03-15T01:00:00Z",
    )
    iteration_dir = tmp_path / "iterations" / "003"
    iteration_dir.mkdir(parents=True, exist_ok=True)
    (iteration_dir / "prompt.md").write_text("旧 prompt\n", encoding="utf-8")
    (iteration_dir / "events.jsonl").write_text("旧 events\n", encoding="utf-8")

    attempt = next_iteration_attempt(state, iteration_number=3, iteration_dir=iteration_dir)

    assert attempt == 2
    assert state["iteration_attempts"] == {"3": 2}

    second_retry_attempt = next_iteration_attempt(
        state,
        iteration_number=3,
        iteration_dir=iteration_dir,
    )

    assert second_retry_attempt == 3
    assert state["iteration_attempts"] == {"3": 3}


def test_mark_loop_process_started_and_clear_loop_process() -> None:
    state = default_state(
        LoopConfig(goal="连续执行"),
        now_ts="2026-03-15T01:00:00Z",
    )

    mark_loop_process_started(
        state,
        pid=43210,
        started_at="2026-03-15T01:10:00Z",
    )

    assert state["loop_pid"] == 43210
    assert state["loop_started_at"] == "2026-03-15T01:10:00Z"

    clear_loop_process(state)

    assert state["loop_pid"] is None
    assert state["loop_started_at"] == ""


def test_is_pid_running_detects_current_process() -> None:
    assert is_pid_running(None) is False
    assert is_pid_running(-1) is False
    assert is_pid_running(999999) is False
    assert is_pid_running(os.getpid()) is True


def test_prepare_state_for_resume_resets_failures_and_runtime_markers() -> None:
    state = default_state(
        LoopConfig(goal="连续执行"),
        now_ts="2026-03-15T01:00:00Z",
    )
    state["status"] = "too_many_failures"
    state["consecutive_failures"] = 3
    state["active_iteration"] = 2
    state["active_iteration_started_at"] = "2026-03-15T01:05:00Z"
    state["active_iteration_dir"] = "/tmp/agent-loop/iterations/002"
    state["loop_pid"] = 32100
    state["loop_started_at"] = "2026-03-15T01:05:00Z"

    prepare_state_for_resume(
        state,
        resume_reason="resume_after_process_missing",
        now_ts="2026-03-15T02:00:00Z",
    )

    assert state["status"] == "running"
    assert state["consecutive_failures"] == 0
    assert state["active_iteration"] is None
    assert state["loop_pid"] is None
    assert state["resume_count"] == 1
    assert state["last_resume_at"] == "2026-03-15T02:00:00Z"
    assert state["last_resume_reason"] == "resume_after_process_missing"


def test_should_auto_resume_only_for_recoverable_non_terminal_states() -> None:
    state = default_state(
        LoopConfig(goal="连续执行"),
        now_ts="2026-03-15T01:00:00Z",
    )
    queue_summary = {"total": 3, "completed": 1, "pending": 2}

    assert (
        should_auto_resume(
            state=state,
            next_action_status="continue",
            queue_summary=queue_summary,
            now_ts="2026-03-15T01:30:00Z",
            loop_pid_running=False,
        )
        is True
    )
    assert (
        should_auto_resume(
            state=state,
            next_action_status="continue",
            queue_summary=queue_summary,
            now_ts="2026-03-15T01:30:00Z",
            loop_pid_running=True,
        )
        is False
    )

    state["status"] = "blocked"
    assert (
        should_auto_resume(
            state=state,
            next_action_status="blocked",
            queue_summary=queue_summary,
            now_ts="2026-03-15T01:30:00Z",
            loop_pid_running=False,
        )
        is False
    )

    state["status"] = "too_many_failures"
    assert (
        should_auto_resume(
            state=state,
            next_action_status="continue",
            queue_summary=queue_summary,
            now_ts="2026-03-15T01:30:00Z",
            loop_pid_running=False,
        )
        is True
    )

    state["status"] = "deadline_reached"
    assert (
        should_auto_resume(
            state=state,
            next_action_status="continue",
            queue_summary=queue_summary,
            now_ts="2026-03-15T01:30:00Z",
            loop_pid_running=False,
        )
        is False
    )


def test_summarize_task_queue_counts_checkbox_items() -> None:
    summary = summarize_task_queue(
        """
        # Queue
        - [x] 已完成 A
        - [ ] 待处理 B
        - [ ] 待处理 C
        """
    )

    assert summary["total"] == 3
    assert summary["completed"] == 1
    assert summary["pending"] == 2


def test_parse_next_action_status_defaults_to_continue() -> None:
    assert parse_next_action_status("Status: completed\n") == "completed"
    assert parse_next_action_status("status: blocked\n") == "blocked"
    assert parse_next_action_status("下一步：继续推进\n") == "continue"


def test_read_goal_text_strips_markdown_heading(tmp_path: Path) -> None:
    goal_path = tmp_path / "GOAL.md"
    goal_path.write_text("# Goal\n\n持续推进仓库任务\n", encoding="utf-8")

    assert read_goal_text(goal_path) == "持续推进仓库任务"


def test_determine_stop_reason_honors_status_deadline_and_failures() -> None:
    state = {
        "deadline_at": "2026-03-15T11:00:00Z",
        "iteration_count": 2,
        "max_iterations": 5,
        "consecutive_failures": 0,
        "max_consecutive_failures": 3,
    }
    queue_summary = {"total": 2, "completed": 1, "pending": 1}

    assert (
        determine_stop_reason(
            state,
            next_action_status="completed",
            queue_summary=queue_summary,
            now_ts="2026-03-15T01:30:00Z",
        )
        == "completed"
    )
    assert (
        determine_stop_reason(
            state,
            next_action_status="continue",
            queue_summary=queue_summary,
            now_ts="2026-03-15T12:00:00Z",
        )
        == "deadline_reached"
    )

    state["iteration_count"] = 5
    state["consecutive_failures"] = 0
    assert (
        determine_stop_reason(
            state,
            next_action_status="continue",
            queue_summary=queue_summary,
            now_ts="2026-03-15T01:30:00Z",
        )
        == "max_iterations_reached"
    )

    state["iteration_count"] = 2
    state["consecutive_failures"] = 3
    assert (
        determine_stop_reason(
            state,
            next_action_status="continue",
            queue_summary=queue_summary,
            now_ts="2026-03-15T01:30:00Z",
        )
        == "too_many_failures"
    )


def test_resolve_iteration_timeout_seconds_caps_to_remaining_deadline() -> None:
    state = default_state(
        LoopConfig(goal="连续执行"),
        now_ts="2026-03-15T01:00:00Z",
    )
    state["deadline_at"] = "2026-03-15T01:05:10Z"

    assert (
        resolve_iteration_timeout_seconds(
            state=state,
            configured_timeout_seconds=1800,
            now_ts="2026-03-15T01:05:00Z",
        )
        == 10
    )
    assert (
        resolve_iteration_timeout_seconds(
            state=state,
            configured_timeout_seconds=5,
            now_ts="2026-03-15T01:05:00Z",
        )
        == 5
    )


def test_build_iteration_prompt_mentions_runtime_contract(tmp_path: Path) -> None:
    config = LoopConfig(goal="连续推进", state_dir=tmp_path)
    paths = runtime_paths(config.state_dir)
    initialize_runtime_files(config, paths)
    state = load_or_create_state(config, paths, now_ts="2026-03-15T01:00:00Z")

    prompt = build_iteration_prompt(config, paths, state)

    assert "你是一个新的 Codex 会话" in prompt
    assert "TASK_QUEUE.md" in prompt
    assert "NEXT_ACTION.md" in prompt
    assert "LOOP_MEMORY.md" in prompt
    assert "docs/agent-runs/" in prompt


def test_build_handoff_prompt_includes_last_message(tmp_path: Path) -> None:
    config = LoopConfig(goal="连续推进", state_dir=tmp_path)
    paths = runtime_paths(config.state_dir)
    initialize_runtime_files(config, paths)
    state = load_or_create_state(config, paths, now_ts="2026-03-15T01:00:00Z")

    handoff = build_handoff_prompt(
        config,
        paths,
        state,
        last_message="本轮已完成脚本骨架，下一步补测试。",
    )

    assert "新的 Codex 对话" in handoff
    assert "本轮已完成脚本骨架" in handoff
    assert "state.json" in handoff
    assert "TASK_QUEUE.md" in handoff


def test_build_watch_progress_report_summarizes_runtime_state(tmp_path: Path) -> None:
    config = LoopConfig(goal="连续推进", state_dir=tmp_path)
    paths = runtime_paths(config.state_dir)
    initialize_runtime_files(config, paths)
    state = load_or_create_state(config, paths, now_ts="2026-03-15T01:00:00Z")
    state["status"] = "running"
    state["iteration_count"] = 5
    state["max_iterations"] = 40
    state["active_iteration"] = 6
    state["active_iteration_dir"] = str(tmp_path / "iterations" / "006")
    state["active_iteration_last_progress_at"] = "2026-03-15T01:45:00Z"
    state["resume_count"] = 2
    state["last_resume_reason"] = "resume_after_too_many_failures"
    state["updated_at"] = "2026-03-15T01:30:00Z"
    paths.task_queue_path.write_text(
        "\n".join(
            [
                "# Task Queue",
                "",
                "- [x] 已完成 A",
                "- [x] 已完成 B",
                "- [ ] 待处理 C",
                "",
            ]
        ),
        encoding="utf-8",
    )
    paths.next_action_path.write_text(
        "# Next Action\n\nStatus: continue\n\n下一轮首要动作：\n- 继续推进\n",
        encoding="utf-8",
    )

    report = build_watch_progress_report(
        paths=paths,
        state=state,
        now_ts="2026-03-15T02:00:00Z",
    )

    assert "Progress report" in report
    assert "status=running" in report
    assert "next_action=continue" in report
    assert "queue=2/3 completed" in report
    assert "pending=1" in report
    assert "active_iteration=6" in report
    assert "active_last_progress=2026-03-15T01:45:00Z" in report
    assert "resume_count=2" in report
    assert "resume_after_too_many_failures" in report


def test_build_watch_progress_report_falls_back_to_active_iteration_artifact_mtime(
    tmp_path: Path,
) -> None:
    config = LoopConfig(goal="连续推进", state_dir=tmp_path)
    paths = runtime_paths(config.state_dir)
    initialize_runtime_files(config, paths)
    state = load_or_create_state(config, paths, now_ts="2026-03-15T01:00:00Z")
    state["status"] = "running"
    state["iteration_count"] = 5
    state["max_iterations"] = 40
    state["loop_pid"] = os.getpid()
    state["active_iteration"] = 6
    iteration_dir = paths.iterations_dir / "006"
    iteration_dir.mkdir(parents=True, exist_ok=True)
    state["active_iteration_dir"] = str(iteration_dir)
    state["active_iteration_last_progress_at"] = ""
    state["resume_count"] = 2
    state["last_resume_reason"] = "resume_after_too_many_failures"
    state["updated_at"] = "2026-03-15T01:30:00Z"
    paths.task_queue_path.write_text(
        "\n".join(
            [
                "# Task Queue",
                "",
                "- [x] 已完成 A",
                "- [ ] 待处理 B",
                "",
            ]
        ),
        encoding="utf-8",
    )
    paths.next_action_path.write_text(
        "# Next Action\n\nStatus: continue\n\n下一轮首要动作：\n- 继续推进\n",
        encoding="utf-8",
    )
    events_path = iteration_dir / "events.jsonl"
    events_path.write_text('{"type":"thread.started"}\n', encoding="utf-8")
    latest_progress = datetime(2026, 3, 15, 1, 46, 30, tzinfo=timezone.utc).timestamp()
    os.utime(events_path, (latest_progress, latest_progress))

    report = build_watch_progress_report(
        paths=paths,
        state=state,
        now_ts="2026-03-15T02:00:00Z",
    )

    assert "active_iteration=6" in report
    assert "active_last_progress=2026-03-15T01:46:30Z" in report


def test_build_watch_progress_report_marks_stale_active_iteration_and_keeps_last_progress(
    tmp_path: Path,
) -> None:
    config = LoopConfig(goal="连续推进", state_dir=tmp_path)
    paths = runtime_paths(config.state_dir)
    initialize_runtime_files(config, paths)
    state = load_or_create_state(config, paths, now_ts="2026-03-15T01:00:00Z")
    state["status"] = "running"
    state["iteration_count"] = 5
    state["max_iterations"] = 40
    state["loop_pid"] = os.getpid()
    state["active_iteration"] = 6
    iteration_dir = paths.iterations_dir / "006"
    iteration_dir.mkdir(parents=True, exist_ok=True)
    state["active_iteration_dir"] = str(iteration_dir)
    state["active_iteration_last_progress_at"] = ""
    stale_child = subprocess.Popen(["python3", "-c", "pass"])
    stale_child.wait(timeout=5)
    assert stale_child.returncode == 0
    state["active_child_pid"] = stale_child.pid
    state["resume_count"] = 2
    state["last_resume_reason"] = "resume_after_too_many_failures"
    state["updated_at"] = "2026-03-15T01:30:00Z"
    paths.task_queue_path.write_text(
        "\n".join(
            [
                "# Task Queue",
                "",
                "- [x] 已完成 A",
                "- [ ] 待处理 B",
                "",
            ]
        ),
        encoding="utf-8",
    )
    paths.next_action_path.write_text(
        "# Next Action\n\nStatus: continue\n\n下一轮首要动作：\n- 继续推进\n",
        encoding="utf-8",
    )
    events_path = iteration_dir / "events.jsonl"
    events_path.write_text('{"type":"turn.failed"}\n', encoding="utf-8")
    latest_progress = datetime(2026, 3, 15, 1, 47, 15, tzinfo=timezone.utc).timestamp()
    os.utime(events_path, (latest_progress, latest_progress))

    report = build_watch_progress_report(
        paths=paths,
        state=state,
        now_ts="2026-03-15T02:00:00Z",
    )

    assert live_active_iteration_number(state) == 0
    assert "active_iteration=6" in report
    assert "active_state=stale" in report
    assert "active_last_progress=2026-03-15T01:47:15Z" in report


def test_build_handoff_prompt_prefers_latest_on_disk_diagnostics_when_state_lags(
    tmp_path: Path,
) -> None:
    config = LoopConfig(goal="连续推进", state_dir=tmp_path)
    paths = runtime_paths(config.state_dir)
    initialize_runtime_files(config, paths)
    state = load_or_create_state(config, paths, now_ts="2026-03-15T01:00:00Z")
    state["iteration_count"] = 7
    state["history"] = [
        {
            "iteration": 7,
            "started_at": "2026-03-15T01:07:00Z",
            "finished_at": "2026-03-15T01:08:00Z",
            "thread_id": "fake-thread-007",
            "return_code": 1,
            "result": "error",
        }
    ]

    iteration_007 = paths.iterations_dir / "007"
    iteration_007.mkdir(parents=True, exist_ok=True)
    (iteration_007 / "diagnostics.json").write_text("{}", encoding="utf-8")

    iteration_009 = paths.iterations_dir / "009"
    iteration_009.mkdir(parents=True, exist_ok=True)
    (iteration_009 / "events.jsonl").write_text('{"type":"thread.started"}\n', encoding="utf-8")
    (iteration_009 / "diagnostics.json").write_text("{}", encoding="utf-8")

    handoff = build_handoff_prompt(
        config,
        paths,
        state,
        last_message="本轮失败，请继续排查。",
    )

    assert "iterations/009/diagnostics.json" in handoff
    assert "iterations/007/diagnostics.json" not in handoff


def test_build_handoff_prompt_omits_stale_diagnostics_when_newer_iteration_has_no_failure_file(
    tmp_path: Path,
) -> None:
    config = LoopConfig(goal="连续推进", state_dir=tmp_path)
    paths = runtime_paths(config.state_dir)
    initialize_runtime_files(config, paths)
    state = load_or_create_state(config, paths, now_ts="2026-03-15T01:00:00Z")
    state["iteration_count"] = 7
    state["history"] = [
        {
            "iteration": 7,
            "started_at": "2026-03-15T01:07:00Z",
            "finished_at": "2026-03-15T01:08:00Z",
            "thread_id": "fake-thread-007",
            "return_code": 1,
            "result": "error",
        }
    ]

    iteration_007 = paths.iterations_dir / "007"
    iteration_007.mkdir(parents=True, exist_ok=True)
    (iteration_007 / "diagnostics.json").write_text("{}", encoding="utf-8")

    iteration_008 = paths.iterations_dir / "008"
    iteration_008.mkdir(parents=True, exist_ok=True)
    (iteration_008 / "events.jsonl").write_text('{"type":"thread.started"}\n', encoding="utf-8")
    (iteration_008 / "last-message.md").write_text(
        "新一轮已有产物，但没有失败诊断。\n",
        encoding="utf-8",
    )

    handoff = build_handoff_prompt(
        config,
        paths,
        state,
        last_message="请基于最新产物继续。",
    )

    assert "diagnostics.json" not in handoff


def test_build_handoff_prompt_prioritizes_live_active_iteration_over_stale_diagnostics(
    tmp_path: Path,
) -> None:
    config = LoopConfig(goal="连续推进", state_dir=tmp_path)
    paths = runtime_paths(config.state_dir)
    initialize_runtime_files(config, paths)
    state = load_or_create_state(config, paths, now_ts="2026-03-15T01:00:00Z")
    state["iteration_count"] = 8
    state["loop_pid"] = os.getpid()
    state["active_iteration"] = 9
    state["active_iteration_started_at"] = "2026-03-15T01:09:00Z"
    state["active_iteration_dir"] = str(paths.iterations_dir / "009")
    state["active_iteration_attempt"] = 2
    state["active_iteration_last_progress_at"] = "2026-03-15T01:09:30Z"
    state["active_child_pid"] = os.getpid()

    iteration_009 = paths.iterations_dir / "009"
    iteration_009.mkdir(parents=True, exist_ok=True)
    (iteration_009 / "prompt.md").write_text("当前轮次提示词\n", encoding="utf-8")
    (iteration_009 / "events.jsonl").write_text('{"type":"thread.started"}\n', encoding="utf-8")
    (iteration_009 / "diagnostics.json").write_text("{}", encoding="utf-8")

    handoff = build_handoff_prompt(
        config,
        paths,
        state,
        last_message="当前主循环仍在执行。",
    )

    assert "iterations/009/prompt.md" in handoff
    assert "iterations/009/events.jsonl" in handoff
    assert "iterations/009/diagnostics.json" not in handoff
    assert "attempt=2" in handoff
    assert "last_progress_at=2026-03-15T01:09:30Z" in handoff
    assert f"child_pid={os.getpid()}" in handoff


def test_build_handoff_prompt_falls_back_to_active_iteration_artifact_mtime(
    tmp_path: Path,
) -> None:
    config = LoopConfig(goal="连续推进", state_dir=tmp_path)
    paths = runtime_paths(config.state_dir)
    initialize_runtime_files(config, paths)
    state = load_or_create_state(config, paths, now_ts="2026-03-15T01:00:00Z")
    state["iteration_count"] = 8
    state["loop_pid"] = os.getpid()
    state["active_iteration"] = 9
    state["active_iteration_started_at"] = "2026-03-15T01:09:00Z"
    iteration_dir = paths.iterations_dir / "009"
    iteration_dir.mkdir(parents=True, exist_ok=True)
    state["active_iteration_dir"] = str(iteration_dir)
    state["active_iteration_attempt"] = 2
    state["active_iteration_last_progress_at"] = ""
    state["active_child_pid"] = os.getpid()

    prompt_path = iteration_dir / "prompt.md"
    prompt_path.write_text("当前轮次提示词\n", encoding="utf-8")
    events_path = iteration_dir / "events.jsonl"
    events_path.write_text('{"type":"thread.started"}\n', encoding="utf-8")
    (iteration_dir / "diagnostics.json").write_text("{}", encoding="utf-8")
    prompt_mtime = datetime(2026, 3, 15, 1, 9, 30, tzinfo=timezone.utc).timestamp()
    latest_progress = datetime(2026, 3, 15, 1, 9, 45, tzinfo=timezone.utc).timestamp()
    os.utime(prompt_path, (prompt_mtime, prompt_mtime))
    os.utime(events_path, (latest_progress, latest_progress))

    handoff = build_handoff_prompt(
        config,
        paths,
        state,
        last_message="当前主循环仍在执行。",
    )

    assert "iterations/009/prompt.md" in handoff
    assert "iterations/009/events.jsonl" in handoff
    assert "iterations/009/diagnostics.json" not in handoff
    assert "attempt=2" in handoff
    assert "last_progress_at=2026-03-15T01:09:45Z" in handoff
    assert f"child_pid={os.getpid()}" in handoff


def test_build_handoff_prompt_surfaces_stale_active_iteration_context(tmp_path: Path) -> None:
    config = LoopConfig(goal="连续推进", state_dir=tmp_path)
    paths = runtime_paths(config.state_dir)
    initialize_runtime_files(config, paths)
    state = load_or_create_state(config, paths, now_ts="2026-03-15T01:00:00Z")
    state["iteration_count"] = 8
    state["loop_pid"] = os.getpid()
    state["active_iteration"] = 9
    iteration_dir = paths.iterations_dir / "009"
    iteration_dir.mkdir(parents=True, exist_ok=True)
    state["active_iteration_dir"] = str(iteration_dir)
    state["active_iteration_attempt"] = 3
    state["active_iteration_last_progress_at"] = ""
    stale_child = subprocess.Popen(["python3", "-c", "pass"])
    stale_child.wait(timeout=5)
    assert stale_child.returncode == 0
    state["active_child_pid"] = stale_child.pid
    events_path = iteration_dir / "events.jsonl"
    events_path.write_text('{"type":"turn.failed"}\n', encoding="utf-8")
    latest_progress = datetime(2026, 3, 15, 1, 9, 50, tzinfo=timezone.utc).timestamp()
    os.utime(events_path, (latest_progress, latest_progress))
    (iteration_dir / "diagnostics.json").write_text("{}", encoding="utf-8")

    handoff = build_handoff_prompt(
        config,
        paths,
        state,
        last_message="当前主循环未完成收口。",
    )

    assert "未收口的活动轮次标记" in handoff
    assert "iteration=9" in handoff
    assert "state=stale" in handoff
    assert "last_progress_at=2026-03-15T01:09:50Z" in handoff
    assert "不要把它当成 live child" in handoff


def test_prepare_iteration_directory_cleans_stale_retry_artifacts(tmp_path: Path) -> None:
    paths = runtime_paths(tmp_path / "agent-loop")
    iteration_dir = paths.iterations_dir / "002"
    iteration_dir.mkdir(parents=True, exist_ok=True)
    (iteration_dir / "prompt.md").write_text("旧 prompt\n", encoding="utf-8")
    (iteration_dir / "events.jsonl").write_text("旧 events\n", encoding="utf-8")
    (iteration_dir / "last-message.md").write_text("旧 message\n", encoding="utf-8")
    (iteration_dir / "diagnostics.json").write_text("{}", encoding="utf-8")
    (iteration_dir / "stderr.log").write_text("旧 stderr\n", encoding="utf-8")
    (iteration_dir / "keep.txt").write_text("保留文件\n", encoding="utf-8")

    prepared_dir = prepare_iteration_directory(paths, 2)

    assert prepared_dir == iteration_dir
    assert not (iteration_dir / "prompt.md").exists()
    assert not (iteration_dir / "events.jsonl").exists()
    assert not (iteration_dir / "last-message.md").exists()
    assert not (iteration_dir / "diagnostics.json").exists()
    assert not (iteration_dir / "stderr.log").exists()
    assert (iteration_dir / "keep.txt").read_text(encoding="utf-8") == "保留文件\n"


def test_build_codex_exec_command_uses_json_output_and_prompt_stdin(tmp_path: Path) -> None:
    config = LoopConfig(goal="连续推进", state_dir=tmp_path, model="gpt-5", search_enabled=True)
    command = build_codex_exec_command(
        config=config,
        repo_root=Path("/repo"),
        last_message_path=Path("/tmp/last-message.md"),
    )

    assert command[:3] == ["codex", "exec", "--json"]
    assert "--skip-git-repo-check" in command
    assert "--search" in command
    assert "-m" in command
    assert "gpt-5" in command
    assert "-o" in command
    assert "/tmp/last-message.md" in command
    assert command[-1] == "-"


def test_build_loop_launcher_command_includes_resumeable_arguments(tmp_path: Path) -> None:
    config = LoopConfig(
        goal="连续推进",
        state_dir=tmp_path,
        duration_hours=6.0,
        max_iterations=12,
        max_consecutive_failures=4,
        max_seconds_per_iteration=900,
        codex_bin="/tmp/fake-codex",
        model="gpt-5",
        search_enabled=True,
    )

    command = build_loop_launcher_command(config)

    assert command[0] == sys.executable
    assert command[1].endswith("scripts/continuous_task_loop.py")
    assert "--state-dir" in command
    assert str(tmp_path) in command
    assert "--goal" in command
    assert "连续推进" in command
    assert "--codex-bin" in command
    assert "/tmp/fake-codex" in command
    assert "--search" in command


def test_continuous_task_loop_dry_run_creates_runtime_files(tmp_path: Path) -> None:
    script_path = ROOT_DIR / "scripts" / "continuous_task_loop.py"
    state_dir = tmp_path / "agent-loop"

    result = subprocess.run(
        [
            "python3",
            str(script_path),
            "--goal",
            "持续推进演示项目",
            "--state-dir",
            str(state_dir),
            "--dry-run",
            "--max-iterations",
            "1",
        ],
        cwd=ROOT_DIR,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    assert (state_dir / "state.json").exists()
    assert (state_dir / "HANDOFF_PROMPT.md").exists()
    assert "dry-run" in result.stdout.lower()


def test_continuous_task_loop_non_dry_run_tracks_active_iteration_with_fake_codex(
    tmp_path: Path,
) -> None:
    script_path = ROOT_DIR / "scripts" / "continuous_task_loop.py"
    state_dir = tmp_path / "agent-loop"
    fake_codex_path = tmp_path / "fake-codex"
    write_fake_codex_bin(fake_codex_path)

    process = subprocess.Popen(
        [
            "python3",
            str(script_path),
            "--goal",
            "验证 non-dry-run 单轮循环",
            "--state-dir",
            str(state_dir),
            "--codex-bin",
            str(fake_codex_path),
            "--max-iterations",
            "1",
            "--max-seconds-per-iteration",
            "30",
        ],
        cwd=ROOT_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    assert process.stdout is not None
    state_path = state_dir / "state.json"
    observed_active_iteration = False
    observed_active_child_pid = False
    observed_active_progress_at = False
    deadline = time.monotonic() + 10.0
    while time.monotonic() < deadline:
        if state_path.exists():
            try:
                state = json.loads(state_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                time.sleep(0.05)
                continue
            if state.get("active_iteration") == 1:
                observed_active_iteration = True
                assert state["active_iteration_started_at"]
                assert state["active_iteration_dir"].endswith("iterations/001")
                assert state["active_iteration_attempt"] == 1
                if state.get("active_iteration_last_progress_at"):
                    observed_active_progress_at = True
                if state.get("active_child_pid"):
                    observed_active_child_pid = True
                if observed_active_child_pid and observed_active_progress_at:
                    break
        time.sleep(0.05)

    stdout, _ = process.communicate(timeout=30)

    assert observed_active_iteration, stdout
    assert observed_active_child_pid, stdout
    assert observed_active_progress_at, stdout
    assert process.returncode == 0, stdout
    assert "Loop stopped: max_iterations_reached" in stdout

    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["status"] == "max_iterations_reached"
    assert state["iteration_count"] == 1
    assert state["active_iteration"] is None
    assert state["active_iteration_started_at"] == ""
    assert state["active_iteration_dir"] == ""
    assert state["active_iteration_attempt"] is None
    assert state["active_iteration_last_progress_at"] == ""
    assert state["active_child_pid"] is None
    assert state["last_thread_id"] == "fake-thread-001"
    assert state["last_stop_reason"] == "max_iterations_reached"
    assert state["history"][-1]["result"] == "ok"
    assert state["history"][-1]["attempt"] == 1

    iteration_dir = state_dir / "iterations" / "001"
    assert (iteration_dir / "prompt.md").exists()
    assert (iteration_dir / "events.jsonl").exists()
    assert (iteration_dir / "last-message.md").read_text(encoding="utf-8").strip() == (
        "Fake child completed verification."
    )
    assert (iteration_dir / "stderr.log").exists()

    handoff_text = (state_dir / "HANDOFF_PROMPT.md").read_text(encoding="utf-8")
    assert "Fake child completed verification." in handoff_text
    assert "NEXT_ACTION.md" in handoff_text


def test_continuous_task_loop_propagates_failure_at_max_iterations(tmp_path: Path) -> None:
    script_path = ROOT_DIR / "scripts" / "continuous_task_loop.py"
    state_dir = tmp_path / "agent-loop"
    fake_codex_path = tmp_path / "fake-codex-fail"
    write_failing_fake_codex_bin(fake_codex_path)

    result = subprocess.run(
        [
            "python3",
            str(script_path),
            "--goal",
            "验证失败轮次不会被 max-iterations 掩盖",
            "--state-dir",
            str(state_dir),
            "--codex-bin",
            str(fake_codex_path),
            "--max-iterations",
            "1",
            "--max-seconds-per-iteration",
            "30",
        ],
        cwd=ROOT_DIR,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1, result.stderr or result.stdout
    assert "Loop stopped: max_iterations_reached" in result.stdout

    state = json.loads((state_dir / "state.json").read_text(encoding="utf-8"))
    assert state["status"] == "max_iterations_reached"
    assert state["iteration_count"] == 1
    assert state["last_thread_id"] == "fake-thread-err-001"
    assert state["last_stop_reason"] == "max_iterations_reached"
    assert state["history"][-1]["return_code"] == 1
    assert state["history"][-1]["result"] == "error"
    assert state["history"][-1]["attempt"] == 1

    diagnostics = json.loads(
        (state_dir / "iterations" / "001" / "diagnostics.json").read_text(encoding="utf-8")
    )
    assert diagnostics["iteration"] == 1
    assert diagnostics["attempt"] == 1
    assert diagnostics["child_pid"] > 0
    assert diagnostics["return_code"] == 1
    assert diagnostics["failure_category"] == "websocket_http_error"
    assert diagnostics["transport_errors"][0]["http_status"] == 426
    assert diagnostics["transport_errors"][0]["url"] == "wss://aixj.vip/responses"
    assert diagnostics["transport_error_groups"][0]["count"] == 1
    assert any("WebSocket Upgrade" in hint for hint in diagnostics["recovery_hints"])
    assert "HTTP 426" in diagnostics["summary"]

    handoff_text = (state_dir / "HANDOFF_PROMPT.md").read_text(encoding="utf-8")
    assert "diagnostics.json" in handoff_text
    assert "HTTP 426" in handoff_text


def test_check_once_resumes_interrupted_loop_with_fake_codex(tmp_path: Path) -> None:
    script_path = ROOT_DIR / "scripts" / "continuous_task_loop.py"
    state_dir = tmp_path / "agent-loop"
    fake_codex_path = tmp_path / "fake-codex"
    write_fake_codex_bin(fake_codex_path)

    config = LoopConfig(goal="验证 watchdog 恢复", state_dir=state_dir)
    paths = runtime_paths(state_dir)
    initialize_runtime_files(config, paths)
    state = load_or_create_state(config, paths, now_ts="2026-03-15T01:00:00Z")
    state["status"] = "interrupted"
    state["last_stop_reason"] = "interrupted"
    state["updated_at"] = "2026-03-15T01:10:00Z"
    save_state(paths, state)

    result = subprocess.run(
        [
            "python3",
            str(script_path),
            "--goal",
            "验证 watchdog 恢复",
            "--state-dir",
            str(state_dir),
            "--codex-bin",
            str(fake_codex_path),
            "--max-iterations",
            "1",
            "--max-seconds-per-iteration",
            "30",
            "--check-once",
        ],
        cwd=ROOT_DIR,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    assert "Resumed loop" in result.stdout

    deadline = time.monotonic() + 10.0
    while time.monotonic() < deadline:
        state = json.loads(paths.state_path.read_text(encoding="utf-8"))
        if state.get("status") == "max_iterations_reached":
            break
        time.sleep(0.05)
    else:
        raise AssertionError(paths.state_path.read_text(encoding="utf-8"))

    state = json.loads(paths.state_path.read_text(encoding="utf-8"))
    assert state["iteration_count"] == 1
    assert state["resume_count"] == 1
    assert state["last_resume_reason"]
    assert state["loop_pid"] is None


def test_check_once_marks_deadline_reached_when_running_process_is_gone(tmp_path: Path) -> None:
    state_dir = tmp_path / "agent-loop"
    config = LoopConfig(goal="验证 watchdog 自动收口", state_dir=state_dir)
    paths = runtime_paths(state_dir)
    initialize_runtime_files(config, paths)
    state = load_or_create_state(config, paths, now_ts="2026-03-15T01:00:00Z")
    state["status"] = "running"
    state["deadline_at"] = "2026-03-15T01:05:00Z"
    state["loop_pid"] = 999999
    state["loop_started_at"] = "2026-03-15T01:01:00Z"
    state["active_iteration"] = 16
    state["active_iteration_started_at"] = "2026-03-15T01:01:00Z"
    state["active_iteration_dir"] = str(state_dir / "iterations" / "016")
    state["active_iteration_attempt"] = 1
    state["active_child_pid"] = 999998
    save_state(paths, state)

    action = run_watchdog_check_once(config, paths)

    assert action == "no_resume"

    state = json.loads(paths.state_path.read_text(encoding="utf-8"))
    assert state["status"] == "deadline_reached"
    assert state["last_stop_reason"] == "deadline_reached"
    assert state["loop_pid"] is None
    assert state["loop_started_at"] == ""
    assert state["active_iteration"] is None
    assert state["active_child_pid"] is None


def test_run_command_streaming_times_out_on_partial_output_without_newline(
    tmp_path: Path,
) -> None:
    child_path = tmp_path / "partial-output-child.py"
    output_path = tmp_path / "events.jsonl"
    write_partial_output_child(child_path)

    started = time.monotonic()
    with pytest.raises(subprocess.TimeoutExpired):
        run_command_streaming(
            command=[sys.executable, str(child_path)],
            cwd=ROOT_DIR,
            input_text="验证 partial output timeout\n",
            output_path=output_path,
            timeout_seconds=1,
        )
    elapsed = time.monotonic() - started

    assert elapsed < 1.8
    assert "partial output without newline" in output_path.read_text(encoding="utf-8")


def test_watch_mode_emits_progress_report(tmp_path: Path) -> None:
    script_path = ROOT_DIR / "scripts" / "continuous_task_loop.py"
    state_dir = tmp_path / "agent-loop"
    fake_codex_path = tmp_path / "fake-codex"
    write_fake_codex_bin(fake_codex_path)

    config = LoopConfig(goal="验证 watchdog 进度播报", state_dir=state_dir)
    paths = runtime_paths(state_dir)
    initialize_runtime_files(config, paths)
    state = load_or_create_state(config, paths, now_ts="2026-03-15T01:00:00Z")
    state["status"] = "interrupted"
    state["last_stop_reason"] = "interrupted"
    state["updated_at"] = "2026-03-15T01:10:00Z"
    save_state(paths, state)

    result = subprocess.run(
        [
            "python3",
            str(script_path),
            "--goal",
            "验证 watchdog 进度播报",
            "--state-dir",
            str(state_dir),
            "--codex-bin",
            str(fake_codex_path),
            "--max-iterations",
            "1",
            "--max-seconds-per-iteration",
            "30",
            "--watch",
            "--check-interval-minutes",
            "0.001",
            "--progress-report-minutes",
            "0.001",
        ],
        cwd=ROOT_DIR,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    assert "Progress report" in result.stdout
    assert "queue=" in result.stdout
    assert "active_iteration=" in result.stdout


def test_continuous_task_loop_docs_and_gitignore_are_wired() -> None:
    readme_text = (ROOT_DIR / "README.md").read_text(encoding="utf-8")
    runbook_text = (ROOT_DIR / "RUNBOOK.md").read_text(encoding="utf-8")
    doc_text = (ROOT_DIR / "docs" / "continuous-task-loop.md").read_text(encoding="utf-8")
    gitignore_text = (ROOT_DIR / ".gitignore").read_text(encoding="utf-8")

    assert "docs/continuous-task-loop.md" in readme_text
    assert "scripts/continuous_task_loop.py" in readme_text
    assert "--watch" in readme_text
    assert "--check-once" in readme_text
    assert "每 60 分钟输出一次进度摘要" in readme_text
    assert "diagnostics.json" in readme_text
    assert "active_iteration_last_progress_at" in readme_text
    assert "active_iteration_state" in readme_text
    assert "failure_category" in readme_text
    assert "recovery_hints" in readme_text
    assert "scripts/continuous_task_loop.py" in runbook_text
    assert "HANDOFF_PROMPT.md" in runbook_text
    assert "--watch" in runbook_text
    assert "--check-once" in runbook_text
    assert "watchdog.log" in runbook_text
    assert "进度摘要" in runbook_text
    assert "diagnostics.json" in runbook_text
    assert "active_iteration_last_progress_at" in runbook_text
    assert "active_iteration_state" in runbook_text
    assert "failure_category" in runbook_text
    assert "recovery_hints" in runbook_text
    assert "output/agent-loop/" in doc_text
    assert "active_iteration" in doc_text
    assert "active_iteration_last_progress_at" in doc_text
    assert "active_iteration_state" in doc_text
    assert "新的 `codex exec` 会话" in doc_text
    assert "--watch" in doc_text
    assert "--check-once" in doc_text
    assert "watchdog.log" in doc_text
    assert "progress-report-minutes" in doc_text
    assert "diagnostics.json" in doc_text
    assert "failure_category" in doc_text
    assert "recovery_hints" in doc_text
    assert "output/agent-loop/" in gitignore_text
