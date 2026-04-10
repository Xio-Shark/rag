from __future__ import annotations

import argparse
import json
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_HEALTH_TIMEOUT_SECONDS = 5


@dataclass(frozen=True)
class ReleaseStep:
    title: str
    kind: str
    command: tuple[str, ...] = ()
    note: str = ""
    url: str = ""


@dataclass(frozen=True)
class ReleasePhase:
    key: str
    title: str
    goal: str
    steps: tuple[ReleaseStep, ...]


def format_command(command: tuple[str, ...]) -> str:
    return shlex.join(command)


def build_release_plan(base_url: str = DEFAULT_BASE_URL) -> tuple[ReleasePhase, ...]:
    health_url = f"{base_url.rstrip('/')}/v1/health"
    return (
        ReleasePhase(
            key="pre-release",
            title="发布前",
            goal="对齐本地与 CI 门禁，确认迁移、回归和视觉检查都可执行。",
            steps=(
                ReleaseStep(
                    title="升级到当前迁移头，确认本地 schema 可前滚",
                    kind="command",
                    command=("alembic", "upgrade", "head"),
                ),
                ReleaseStep(
                    title="验证迁移契约",
                    kind="command",
                    command=("python3", "-m", "pytest", "-q", "tests/test_database_migrations.py"),
                ),
                ReleaseStep(
                    title="运行静态检查",
                    kind="command",
                    command=("python3", "-m", "ruff", "check", "app", "tests", "scripts"),
                ),
                ReleaseStep(
                    title="运行全量回归",
                    kind="command",
                    command=("python3", "-m", "pytest", "-q"),
                ),
                ReleaseStep(
                    title="运行浏览器级 E2E",
                    kind="command",
                    command=("python3", "-m", "pytest", "-q", "-m", "e2e"),
                ),
                ReleaseStep(
                    title="运行视觉回归 E2E",
                    kind="command",
                    command=(
                        "python3",
                        "-m",
                        "pytest",
                        "-q",
                        "tests/test_e2e_visual_regression.py",
                    ),
                ),
                ReleaseStep(
                    title="校验视觉基线清单与文档同步状态",
                    kind="command",
                    command=("python3", "scripts/render_visual_regression_baselines.py", "--check"),
                ),
                ReleaseStep(
                    title="做一次字节码编译校验",
                    kind="command",
                    command=("python3", "-m", "compileall", "app", "tests", "scripts"),
                ),
            ),
        ),
        ReleasePhase(
            key="release",
            title="发布中",
            goal="在目标环境执行 cutover，并在变更前保留回滚抓手。",
            steps=(
                ReleaseStep(
                    title="保留上一稳定版本的代码、配置和数据库备份",
                    kind="manual",
                    note="SQLite 至少备份 `rag_qa_bench.db`；PostgreSQL 至少保留上一稳定 dump。",
                ),
                ReleaseStep(
                    title="在目标环境应用迁移",
                    kind="command",
                    command=("alembic", "upgrade", "head"),
                ),
                ReleaseStep(
                    title="按目标模式启动服务",
                    kind="manual",
                    note=(
                        "SQLite 模式可直接启动；PostgreSQL + pgvector 模式需先准备 `.env` 并确保 "
                        "`docker compose up -d` 已完成。"
                    ),
                ),
                ReleaseStep(
                    title="核对本次发布计划对应的 feature flag",
                    kind="manual",
                    note=(
                        "确认 `FEATURE_EVALS_ENABLED` 和 "
                        "`FEATURE_REPLAY_EXPERIMENTS_ENABLED` 符合预期。"
                    ),
                ),
            ),
        ),
        ReleasePhase(
            key="post-release",
            title="发布后",
            goal="确认服务健康、核心查询与评测烟雾链路仍然可用。",
            steps=(
                ReleaseStep(
                    title="检查健康状态并记录数据库后端、嵌入存储和 feature flags",
                    kind="health",
                    url=health_url,
                ),
                ReleaseStep(
                    title="执行一次搜索烟雾检查",
                    kind="command",
                    command=("python3", "-m", "app.cli.search", "--query", "系统支持什么"),
                ),
                ReleaseStep(
                    title="执行一次离线评测烟雾检查",
                    kind="command",
                    command=(
                        "python3",
                        "-m",
                        "app.cli.eval",
                        "run",
                        "--dataset",
                        "baseline_v1",
                        "--snapshot",
                        "default",
                    ),
                ),
            ),
        ),
    )


def select_phases(
    phases: Iterable[ReleasePhase],
    selected_keys: list[str] | None,
) -> tuple[ReleasePhase, ...]:
    if not selected_keys:
        return tuple(phases)
    selected_key_set = set(selected_keys)
    return tuple(phase for phase in phases if phase.key in selected_key_set)


def render_release_plan(phases: Iterable[ReleasePhase], execute: bool) -> str:
    lines = [
        "Release Gate",
        "",
        (
            "当前模式：execute"
            if execute
            else "当前模式：dry-run（只输出阶段与命令，不实际执行）"
        ),
        "",
    ]

    for phase in phases:
        lines.append(f"[{phase.key}] {phase.title}")
        lines.append(f"目标：{phase.goal}")
        for index, step in enumerate(phase.steps, start=1):
            if step.kind == "command":
                lines.append(f"{index}. 命令：{step.title}")
                lines.append(f"   {format_command(step.command)}")
                continue
            if step.kind == "health":
                lines.append(f"{index}. 健康检查：{step.title}")
                lines.append(f"   GET {step.url}")
                continue
            lines.append(f"{index}. 手工检查：{step.title}")
            lines.append(f"   {step.note}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def check_health(url: str, timeout_seconds: int = DEFAULT_HEALTH_TIMEOUT_SECONDS) -> dict:
    try:
        with urlopen(url, timeout=timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise RuntimeError(f"健康检查失败，HTTP {exc.code}: {url}") from exc
    except URLError as exc:
        raise RuntimeError(f"健康检查失败，无法访问 {url}: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"健康检查失败，返回不是合法 JSON: {url}") from exc

    if not payload.get("database_ok"):
        raise RuntimeError(f"健康检查失败，database_ok 不是 true: {url}")
    if not isinstance(payload.get("feature_flags"), dict):
        raise RuntimeError(f"健康检查失败，缺少 feature_flags: {url}")
    return payload


def run_release_plan(phases: Iterable[ReleasePhase], execute: bool) -> None:
    for phase in phases:
        print(f"[{phase.key}] {phase.title}")
        for step in phase.steps:
            if step.kind == "manual":
                print(f"- 手工检查：{step.title}")
                print(f"  {step.note}")
                continue

            if step.kind == "command":
                print(f"- 命令：{format_command(step.command)}")
                if execute:
                    subprocess.run(step.command, cwd=ROOT_DIR, check=True)
                continue

            print(f"- 健康检查：GET {step.url}")
            if execute:
                payload = check_health(step.url, timeout_seconds=DEFAULT_HEALTH_TIMEOUT_SECONDS)
                print(
                    "  "
                    f"database_backend={payload.get('database_backend')} "
                    f"embedding_storage={payload.get('embedding_storage')} "
                    "feature_flags="
                    f"{json.dumps(payload['feature_flags'], ensure_ascii=False, sort_keys=True)}"
                )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="RAG QA Bench 最小 release gate")
    parser.add_argument(
        "--phase",
        action="append",
        choices=["pre-release", "release", "post-release"],
        help="只运行指定阶段；默认按发布前、发布中、发布后顺序全部输出或执行。",
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help="发布后健康检查使用的服务地址，默认 http://127.0.0.1:8000。",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="实际执行命令与健康检查；默认只做 dry-run 输出。",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    phases = select_phases(build_release_plan(args.base_url), args.phase)
    print(render_release_plan(phases, execute=args.execute))
    if args.execute:
        run_release_plan(phases, execute=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
