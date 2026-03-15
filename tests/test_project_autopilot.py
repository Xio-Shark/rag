from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

from scripts.continuous_task_loop import (
    LoopConfig,
    default_state,
    initialize_runtime_files,
    is_pid_running,
    load_or_create_state,
    runtime_paths,
    save_state,
)
from scripts.project_autopilot import (
    AutopilotConfig,
    build_watchdog_command,
    collect_status,
    refresh_state_for_new_run,
)

ROOT_DIR = Path(__file__).resolve().parents[1]


def write_fake_codex_bin(path: Path, sleep_seconds: float = 1.0) -> None:
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
                f"time.sleep({sleep_seconds})",
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


def test_build_watchdog_command_wraps_continuous_task_loop_watch_mode(tmp_path: Path) -> None:
    config = AutopilotConfig(
        goal="连续推进",
        state_dir=tmp_path,
        duration_hours=10.0,
        max_iterations=12,
        max_consecutive_failures=4,
        max_seconds_per_iteration=900,
        check_interval_minutes=15.0,
        codex_bin="/tmp/fake-codex",
        model="gpt-5",
        search_enabled=True,
    )

    command = build_watchdog_command(config)

    assert command[0] == sys.executable
    assert command[1].endswith("scripts/continuous_task_loop.py")
    assert "--watch" in command
    assert "--goal" in command
    assert "连续推进" in command
    assert "--state-dir" in command
    assert str(tmp_path) in command
    assert "--duration-hours" in command
    assert "--check-interval-minutes" in command
    assert "15.0" in command
    assert "--codex-bin" in command
    assert "/tmp/fake-codex" in command
    assert "--search" in command


def test_refresh_state_for_new_run_resets_runtime_window() -> None:
    state = default_state(
        LoopConfig(goal="旧目标"),
        now_ts="2026-03-15T01:00:00Z",
    )
    state["status"] = "deadline_reached"
    state["goal"] = "旧目标"
    state["iteration_count"] = 7
    state["consecutive_failures"] = 2
    state["loop_pid"] = 32100
    state["loop_started_at"] = "2026-03-15T01:10:00Z"
    state["resume_count"] = 3
    state["last_resume_at"] = "2026-03-15T02:00:00Z"
    state["last_resume_reason"] = "resume_after_iteration_timeout"
    state["active_iteration"] = 4
    state["active_iteration_started_at"] = "2026-03-15T02:05:00Z"
    state["active_iteration_dir"] = "/tmp/agent-loop/iterations/004"
    state["history"] = [{"iteration": 1, "result": "ok"}]

    config = AutopilotConfig(goal="新目标", duration_hours=10.0)

    refresh_state_for_new_run(state, config, now_ts="2026-03-16T03:00:00Z")

    assert state["status"] == "running"
    assert state["goal"] == "新目标"
    assert state["started_at"] == "2026-03-16T03:00:00Z"
    assert state["updated_at"] == "2026-03-16T03:00:00Z"
    assert state["deadline_at"] == "2026-03-16T13:00:00Z"
    assert state["duration_hours"] == 10.0
    assert state["iteration_count"] == 0
    assert state["consecutive_failures"] == 0
    assert state["loop_pid"] is None
    assert state["loop_started_at"] == ""
    assert state["resume_count"] == 0
    assert state["last_resume_at"] == ""
    assert state["last_resume_reason"] == ""
    assert state["active_iteration"] is None
    assert state["active_iteration_started_at"] == ""
    assert state["active_iteration_dir"] == ""
    assert state["history"] == []


def test_project_autopilot_start_and_status_cover_terminal_run(tmp_path: Path) -> None:
    script_path = ROOT_DIR / "scripts" / "project_autopilot.py"
    state_dir = tmp_path / "agent-loop"
    fake_codex_path = tmp_path / "fake-codex"
    write_fake_codex_bin(fake_codex_path)

    start_result = subprocess.run(
        [
            "python3",
            str(script_path),
            "start",
            "--goal",
            "验证自动化任务入口",
            "--state-dir",
            str(state_dir),
            "--codex-bin",
            str(fake_codex_path),
            "--max-iterations",
            "1",
            "--max-seconds-per-iteration",
            "30",
            "--check-interval-minutes",
            "0.01",
            "--json",
        ],
        cwd=ROOT_DIR,
        capture_output=True,
        text=True,
        check=False,
    )

    assert start_result.returncode == 0, start_result.stderr or start_result.stdout
    start_payload = json.loads(start_result.stdout)
    assert start_payload["result"] == "started"
    assert Path(start_payload["autopilot_log_path"]).exists()

    state_path = state_dir / "state.json"
    deadline = time.monotonic() + 15.0
    while time.monotonic() < deadline:
        if state_path.exists():
            state = json.loads(state_path.read_text(encoding="utf-8"))
            if state.get("status") == "max_iterations_reached":
                break
        time.sleep(0.05)
    else:
        raise AssertionError(state_path.read_text(encoding="utf-8"))

    status_deadline = time.monotonic() + 10.0
    latest_status: dict[str, object] | None = None
    while time.monotonic() < status_deadline:
        status_result = subprocess.run(
            [
                "python3",
                str(script_path),
                "status",
                "--state-dir",
                str(state_dir),
                "--json",
            ],
            cwd=ROOT_DIR,
            capture_output=True,
            text=True,
            check=False,
        )
        assert status_result.returncode == 0, status_result.stderr or status_result.stdout
        latest_status = json.loads(status_result.stdout)
        if latest_status["autopilot_running"] is False:
            break
        time.sleep(0.1)

    assert latest_status is not None
    assert latest_status["autopilot_running"] is False
    assert latest_status["loop_status"] == "max_iterations_reached"
    assert latest_status["iteration_count"] == 1
    assert latest_status["last_thread_id"] == "fake-thread-001"


def test_collect_status_reports_stale_active_iteration_when_child_has_exited(
    tmp_path: Path,
) -> None:
    state_dir = tmp_path / "agent-loop"
    config = LoopConfig(goal="验证 status stale", state_dir=state_dir)
    paths = runtime_paths(state_dir)
    initialize_runtime_files(config, paths)
    state = load_or_create_state(config, paths, now_ts="2026-03-15T01:00:00Z")
    iteration_dir = state_dir / "iterations" / "001"
    iteration_dir.mkdir(parents=True, exist_ok=True)
    (iteration_dir / "events.jsonl").write_text('{"type":"turn.failed"}\n', encoding="utf-8")
    state["status"] = "running"
    state["loop_pid"] = os.getpid()
    state["active_iteration"] = 1
    state["active_iteration_dir"] = str(iteration_dir)
    state["active_iteration_attempt"] = 2
    state["active_iteration_last_progress_at"] = "2026-03-15T01:05:00Z"
    stale_child = subprocess.Popen(["python3", "-c", "pass"])
    stale_child.wait(timeout=5)
    state["active_child_pid"] = stale_child.pid
    save_state(paths, state)

    payload = collect_status(state_dir)

    assert payload["active_iteration"] == 1
    assert payload["active_iteration_state"] == "stale"
    assert payload["active_iteration_live"] is False
    assert payload["active_iteration_last_progress_at"] == "2026-03-15T01:05:00Z"
    assert payload["latest_failure_iteration"] is None
    assert payload["latest_failure_diagnostics_path"] == ""
    assert payload["latest_failure_attempt"] is None
    assert payload["latest_failure_category"] == ""
    assert payload["latest_failure_summary"] == ""
    assert payload["latest_failure_transport_error_groups"] == []
    assert payload["latest_failure_recovery_hints"] == []


def test_collect_status_surfaces_latest_failure_diagnostics_when_state_lags(
    tmp_path: Path,
) -> None:
    state_dir = tmp_path / "agent-loop"
    config = LoopConfig(goal="验证 status 失败摘要", state_dir=state_dir)
    paths = runtime_paths(state_dir)
    initialize_runtime_files(config, paths)
    state = load_or_create_state(config, paths, now_ts="2026-03-15T01:00:00Z")
    state["status"] = "running"
    state["loop_pid"] = os.getpid()
    state["iteration_count"] = 6
    state["history"] = [
        {
            "iteration": 6,
            "started_at": "2026-03-15T01:00:00Z",
            "finished_at": "2026-03-15T01:10:00Z",
            "thread_id": "fake-thread-006",
            "return_code": 0,
            "result": "ok",
        }
    ]
    state["active_iteration"] = 8
    state["active_iteration_dir"] = str(state_dir / "iterations" / "008")
    state["active_iteration_attempt"] = 1
    state["active_iteration_last_progress_at"] = "2026-03-15T01:15:00Z"
    stale_child = subprocess.Popen(["python3", "-c", "pass"])
    stale_child.wait(timeout=5)
    state["active_child_pid"] = stale_child.pid
    save_state(paths, state)

    diagnostics_path = state_dir / "iterations" / "007" / "diagnostics.json"
    diagnostics_path.parent.mkdir(parents=True, exist_ok=True)
    diagnostics_path.write_text(
        json.dumps(
            {
                "iteration": 7,
                "attempt": 1,
                "thread_id": "fake-thread-007",
                "return_code": 1,
                "failure_category": "dns_lookup_error",
                "transport_error_groups": [
                    {
                        "kind": "dns_lookup_error",
                        "component": "codex_api::endpoint::responses_websocket",
                        "url": "wss://aixj.vip/responses",
                        "http_status": None,
                        "status_reason": "",
                        "count": 4,
                    }
                ],
                "summary": "子会话失败：无法解析地址信息。",
                "recovery_hints": [
                    "检查目标 hostname 的 DNS 解析是否正常。",
                    "确认代理或 VPN 配置对 `codex exec` 生效。",
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    payload = collect_status(state_dir)

    assert payload["active_iteration_state"] == "stale"
    assert payload["latest_failure_iteration"] == 7
    assert payload["latest_failure_diagnostics_path"] == str(diagnostics_path)
    assert payload["latest_failure_attempt"] == 1
    assert payload["latest_failure_category"] == "dns_lookup_error"
    assert payload["latest_failure_summary"] == "子会话失败：无法解析地址信息。"
    assert payload["latest_failure_transport_error_groups"] == [
        {
            "kind": "dns_lookup_error",
            "component": "codex_api::endpoint::responses_websocket",
            "url": "wss://aixj.vip/responses",
            "http_status": None,
            "status_reason": "",
            "count": 4,
        }
    ]
    assert payload["latest_failure_recovery_hints"] == [
        "检查目标 hostname 的 DNS 解析是否正常。",
        "确认代理或 VPN 配置对 `codex exec` 生效。",
    ]


def test_collect_status_normalizes_legacy_failure_diagnostics(
    tmp_path: Path,
) -> None:
    state_dir = tmp_path / "agent-loop"
    config = LoopConfig(goal="验证 legacy diagnostics 兼容", state_dir=state_dir)
    paths = runtime_paths(state_dir)
    initialize_runtime_files(config, paths)
    state = load_or_create_state(config, paths, now_ts="2026-03-15T01:00:00Z")
    state["status"] = "running"
    state["loop_pid"] = os.getpid()
    state["iteration_count"] = 5
    state["history"] = [
        {
            "iteration": 5,
            "started_at": "2026-03-15T01:00:00Z",
            "finished_at": "2026-03-15T01:10:00Z",
            "thread_id": "fake-thread-005",
            "return_code": 0,
            "result": "ok",
        }
    ]
    save_state(paths, state)

    diagnostics_path = state_dir / "iterations" / "006" / "diagnostics.json"
    diagnostics_path.parent.mkdir(parents=True, exist_ok=True)
    diagnostics_path.write_text(
        json.dumps(
            {
                "thread_id": "fake-thread-006",
                "return_code": 1,
                "warnings": [
                    "Under-development features enabled: responses_websockets_v2.",
                ],
                "error_messages": [
                    "Falling back from WebSockets to HTTPS transport. "
                    "stream disconnected before completion: failed to lookup "
                    "address information: nodename nor servname provided, "
                    "or not known"
                ],
                "transport_errors": [
                    {
                        "level": "ERROR",
                        "component": "codex_api::endpoint::responses_websocket",
                        "message": (
                            "failed to connect to websocket: IO error: failed "
                            "to lookup address information: nodename nor "
                            "servname provided, or not known, url: "
                            "wss://aixj.vip/responses"
                        ),
                        "kind": "dns_lookup_error",
                        "http_status": None,
                        "status_reason": "",
                        "url": "wss://aixj.vip/responses",
                    },
                    {
                        "level": "ERROR",
                        "component": "codex_api::endpoint::responses_websocket",
                        "message": (
                            "failed to connect to websocket: IO error: failed "
                            "to lookup address information: nodename nor "
                            "servname provided, or not known, url: "
                            "wss://aixj.vip/responses"
                        ),
                        "kind": "dns_lookup_error",
                        "http_status": None,
                        "status_reason": "",
                        "url": "wss://aixj.vip/responses",
                    },
                ],
                "summary": (
                    "子会话失败：codex_api::endpoint::responses_websocket "
                    "无法解析地址信息，目标 wss://aixj.vip/responses。"
                ),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    payload = collect_status(state_dir)

    assert payload["latest_failure_iteration"] == 6
    assert payload["latest_failure_diagnostics_path"] == str(diagnostics_path)
    assert payload["latest_failure_attempt"] is None
    assert payload["latest_failure_category"] == "dns_lookup_error"
    assert payload["latest_failure_summary"] == (
        "子会话失败：codex_api::endpoint::responses_websocket 无法解析地址信息，目标 "
        "wss://aixj.vip/responses。"
    )
    assert payload["latest_failure_transport_error_groups"] == [
        {
            "kind": "dns_lookup_error",
            "component": "codex_api::endpoint::responses_websocket",
            "url": "wss://aixj.vip/responses",
            "http_status": None,
            "status_reason": "",
            "count": 2,
        }
    ]
    assert any("DNS" in hint for hint in payload["latest_failure_recovery_hints"])
    assert any("warning" in hint for hint in payload["latest_failure_recovery_hints"])


def test_project_autopilot_stop_terminates_watch_and_loop_processes(tmp_path: Path) -> None:
    script_path = ROOT_DIR / "scripts" / "project_autopilot.py"
    state_dir = tmp_path / "agent-loop"
    paths = runtime_paths(state_dir)
    initialize_runtime_files(LoopConfig(goal="验证 stop", state_dir=state_dir), paths)
    state = load_or_create_state(
        LoopConfig(goal="验证 stop", state_dir=state_dir),
        paths,
        now_ts="2026-03-15T01:00:00Z",
    )

    watch_process = subprocess.Popen(["sleep", "30"], start_new_session=True)
    loop_process = subprocess.Popen(["sleep", "30"], start_new_session=True)

    (state_dir / "autopilot.pid").write_text(f"{watch_process.pid}\n", encoding="utf-8")
    state["status"] = "running"
    state["loop_pid"] = loop_process.pid
    state["loop_started_at"] = "2026-03-15T01:05:00Z"
    state["active_iteration"] = 2
    state["active_iteration_started_at"] = "2026-03-15T01:06:00Z"
    state["active_iteration_dir"] = "/tmp/agent-loop/iterations/002"
    save_state(paths, state)

    stop_result = subprocess.run(
        [
            "python3",
            str(script_path),
            "stop",
            "--state-dir",
            str(state_dir),
            "--json",
        ],
        cwd=ROOT_DIR,
        capture_output=True,
        text=True,
        check=False,
    )

    assert stop_result.returncode == 0, stop_result.stderr or stop_result.stdout
    stop_payload = json.loads(stop_result.stdout)
    assert stop_payload["result"] == "stopped"
    assert watch_process.pid in stop_payload["stopped_pids"]
    assert loop_process.pid in stop_payload["stopped_pids"]

    watch_process.wait(timeout=5)
    loop_process.wait(timeout=5)

    assert is_pid_running(watch_process.pid) is False
    assert is_pid_running(loop_process.pid) is False

    state = json.loads(paths.state_path.read_text(encoding="utf-8"))
    assert state["status"] == "interrupted"
    assert state["last_stop_reason"] == "autopilot_stopped"
    assert state["loop_pid"] is None
    assert state["loop_started_at"] == ""
    assert state["active_iteration"] is None
    assert state["active_iteration_started_at"] == ""
    assert state["active_iteration_dir"] == ""
    assert (state_dir / "autopilot.pid").exists() is False


def test_project_autopilot_docs_are_wired() -> None:
    readme_text = (ROOT_DIR / "README.md").read_text(encoding="utf-8")
    runbook_text = (ROOT_DIR / "RUNBOOK.md").read_text(encoding="utf-8")
    doc_text = (ROOT_DIR / "docs" / "continuous-task-loop.md").read_text(encoding="utf-8")

    assert "scripts/project_autopilot.py start" in readme_text
    assert "scripts/project_autopilot.py status" in readme_text
    assert "active_iteration_state" in readme_text
    assert "latest_failure_category" in readme_text
    assert "latest_failure_attempt" in readme_text
    assert "latest_failure_transport_error_groups" in readme_text
    assert "scripts/project_autopilot.py stop" in readme_text
    assert "scripts/project_autopilot.py start" in runbook_text
    assert "active_iteration_state" in runbook_text
    assert "latest_failure_summary" in runbook_text
    assert "latest_failure_transport_error_groups" in runbook_text
    assert "state.json` 标记为 `interrupted`" in runbook_text
    assert "scripts/project_autopilot.py start" in doc_text
    assert "active_iteration_state" in doc_text
    assert "latest_failure_recovery_hints" in doc_text
    assert "latest_failure_attempt" in doc_text
    assert "autopilot.pid" in doc_text
    assert "autopilot.log" in doc_text
