from __future__ import annotations

import socket
import threading
import time
from typing import Generator

import httpx
import pytest
import uvicorn

pytestmark = pytest.mark.e2e


def _pick_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@pytest.fixture()
def live_server(prepared_environment) -> Generator[str, None, None]:
    from app.db.session import get_session_factory, init_database
    from app.main import app
    from app.services.ingestion import DocumentIngestionService

    init_database()
    session = get_session_factory()()
    try:
        DocumentIngestionService(session).import_directory(prepared_environment["docs_dir"])
        session.commit()
    finally:
        session.close()

    port = _pick_free_port()
    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=port,
        log_level="warning",
        lifespan="on",
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    base_url = f"http://127.0.0.1:{port}"
    deadline = time.time() + 15
    client = httpx.Client(base_url=base_url, timeout=1.0)
    try:
        while time.time() < deadline:
            try:
                response = client.get("/v1/health")
                if response.status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            time.sleep(0.1)
        else:
            pytest.fail("测试服务未能在 15 秒内启动")

        yield base_url
    finally:
        client.close()
        server.should_exit = True
        thread.join(timeout=10)


@pytest.fixture()
def browser_page() -> Generator[object, None, None]:
    playwright = pytest.importorskip("playwright.sync_api")
    with playwright.sync_playwright() as runner:
        try:
            browser = runner.chromium.launch()
        except Exception as exc:  # pragma: no cover
            pytest.skip(f"Chromium 不可用，跳过 E2E：{exc}")
        page = browser.new_page(viewport={"width": 1440, "height": 1400})
        try:
            yield page
        finally:
            browser.close()


def _option_value_by_text(page, select_selector: str, text: str) -> str:
    value = page.eval_on_selector(
        select_selector,
        """
        (element, targetText) => {
          const option = Array.from(element.options).find((item) =>
            item.textContent.includes(targetText)
          );
          return option ? option.value : "";
        }
        """,
        text,
    )
    assert value, f"未找到包含 {text!r} 的选项"
    return value


def _run_eval(page, expect, snapshot_name: str) -> None:
    page.select_option("#dataset-select", value="baseline_v1")
    page.select_option("#snapshot-select", value=snapshot_name)
    page.locator("#run-eval-button").click()
    expect(page.locator("#run-eval-output")).to_contain_text(snapshot_name)


def _prepare_compare_runs(page, expect) -> tuple[str, str]:
    _run_eval(page, expect, "default")
    _run_eval(page, expect, "compact_context")

    page.wait_for_function(
        "document.querySelector('#base-run-select').options.length > 2"
    )
    base_run_id = _option_value_by_text(page, "#base-run-select", "default")
    target_run_id = _option_value_by_text(page, "#target-run-select", "compact_context")
    page.select_option("#base-run-select", value=base_run_id)
    page.select_option("#target-run-select", value=target_run_id)
    page.locator("#compare-button").click()
    expect(page.locator("#compare-output")).to_contain_text("新增回归")
    return base_run_id, target_run_id


def test_bad_case_replay_experiment_flow(live_server: str, browser_page) -> None:
    playwright = pytest.importorskip("playwright.sync_api")
    expect = playwright.expect
    page = browser_page

    page.goto(live_server, wait_until="networkidle")
    page.wait_for_function(
        "document.querySelector('#dataset-select').options.length > 1"
    )
    page.wait_for_function(
        "document.querySelector('#snapshot-select').options.length > 1"
    )

    _prepare_compare_runs(page, expect)
    expect(page.locator("#compare-output")).to_contain_text("实验摘要")
    expect(page.locator("#compare-output")).to_contain_text("指标概览")
    expect(page.locator("#compare-output")).to_contain_text("建议动作")
    expect(
        page.locator("#compare-output [data-summary-action='focus-case']")
    ).to_contain_text("去看 bad case")
    page.locator("#compare-output [data-summary-action='focus-case']").click()
    expect(page.locator("#compare-detail-output")).to_contain_text("路线图双事实")

    page.locator("#compare-detail-output .case-button", has_text="重新回放").click()
    expect(page.locator("#replay-output")).to_contain_text("实验 ID")
    expect(page.locator("#replay-context-output")).to_contain_text("路线图双事实")
    expect(page.locator("#replay-history-output")).to_contain_text("compact_context")

    page.select_option("#replay-snapshot-select", value="default")
    page.locator("#replay-top-k-input").fill("3")
    page.locator("#replay-threshold-input").fill("0.12")
    page.locator("#replay-run-button").click()
    expect(page.locator("#replay-output")).to_contain_text("覆盖参数")
    expect(page.locator("#replay-output")).to_contain_text("top_k")
    expect(page.locator("#replay-history-output")).to_contain_text("default")

    page.wait_for_function(
        "document.querySelector('#replay-base-select').options.length > 2"
    )
    base_experiment_id = _option_value_by_text(page, "#replay-base-select", "compact_context")
    target_experiment_id = _option_value_by_text(page, "#replay-target-select", "default")
    page.select_option("#replay-base-select", value=base_experiment_id)
    page.select_option("#replay-target-select", value=target_experiment_id)
    page.locator("#replay-compare-button").click()

    expect(page.locator("#replay-compare-output")).to_contain_text("实验摘要")
    expect(page.locator("#replay-compare-output")).to_contain_text("参数变化")
    expect(page.locator("#replay-compare-output")).to_contain_text("citation_count delta")
    expect(page.locator("#replay-compare-output")).to_contain_text("top_k")
    expect(page.locator("#replay-compare-output")).to_contain_text("对比实验")
    expect(page.locator("#replay-compare-output")).to_contain_text("建议动作")
    expect(
        page.locator("#replay-compare-output [data-summary-action='open-audit']")
    ).to_contain_text("查看审计")
    expect(
        page.locator("#replay-compare-output [data-summary-action='restore-report']")
    ).to_contain_text("恢复完整报告")
    page.locator("#replay-compare-output [data-summary-action='open-audit']").click()
    expect(page.locator("#audit-output")).to_contain_text("审计 ID")
    page.locator("#replay-compare-output [data-summary-action='restore-report']").click()
    expect(page.locator("#report-output")).to_contain_text("# RAG QA Bench 评测报告")


def test_report_panel_syncs_with_compare_case_drilldown(live_server: str, browser_page) -> None:
    playwright = pytest.importorskip("playwright.sync_api")
    expect = playwright.expect
    page = browser_page

    page.goto(live_server, wait_until="networkidle")
    page.wait_for_function(
        "document.querySelector('#dataset-select').options.length > 1"
    )
    page.wait_for_function(
        "document.querySelector('#snapshot-select').options.length > 1"
    )

    _prepare_compare_runs(page, expect)
    page.locator("#compare-output .case-button", has_text="路线图双事实").click()

    expect(page.locator("#compare-detail-output")).to_contain_text("路线图双事实")
    expect(page.locator("#report-meta")).to_contain_text("已定位到 路线图双事实")
    expect(page.locator("#report-output")).to_contain_text("路线图双事实")

    selected_report_run = page.eval_on_selector(
        "#report-run-select",
        "(element) => element.selectedOptions[0]?.textContent || ''",
    )
    assert "compact_context" in selected_report_run


def test_report_read_then_case_drilldown_can_jump_to_audit(live_server: str, browser_page) -> None:
    playwright = pytest.importorskip("playwright.sync_api")
    expect = playwright.expect
    page = browser_page

    page.goto(live_server, wait_until="networkidle")
    page.wait_for_function(
        "document.querySelector('#dataset-select').options.length > 1"
    )
    page.wait_for_function(
        "document.querySelector('#snapshot-select').options.length > 1"
    )

    base_run_id, _ = _prepare_compare_runs(page, expect)
    page.select_option("#report-run-select", value=base_run_id)
    page.select_option("#report-format-select", value="markdown")
    page.locator("#report-button").click()

    expect(page.locator("#report-meta")).to_contain_text("report.md")
    expect(page.locator("#report-output")).to_contain_text("# RAG QA Bench 评测报告")

    page.locator("#compare-output .case-button", has_text="路线图双事实").click()
    expect(page.locator("#report-meta")).to_contain_text("已定位到 路线图双事实")

    page.locator("#compare-detail-output .case-button", has_text="查看审计").last.click()
    expect(page.locator("#audit-output")).to_contain_text("审计 ID")
    expect(page.locator("#document-filter-input")).to_have_value(
        "路线图如何安排 PDF 和多知识库能力？"
    )


def test_report_outline_can_focus_case_and_restore_full_report(
    live_server: str, browser_page
) -> None:
    playwright = pytest.importorskip("playwright.sync_api")
    expect = playwright.expect
    page = browser_page

    page.goto(live_server, wait_until="networkidle")
    page.wait_for_function(
        "document.querySelector('#dataset-select').options.length > 1"
    )
    page.wait_for_function(
        "document.querySelector('#snapshot-select').options.length > 1"
    )

    _, target_run_id = _prepare_compare_runs(page, expect)
    page.select_option("#report-run-select", value=target_run_id)
    page.select_option("#report-format-select", value="markdown")
    page.locator("#report-button").click()

    expect(page.locator("#report-outline-output")).to_contain_text("路线图双事实")
    page.locator("#report-outline-output .outline-button", has_text="路线图双事实").click()
    expect(page.locator("#report-meta")).to_contain_text("已定位到 路线图双事实")
    expect(page.locator("#report-output")).to_contain_text("路线图双事实")
    expect(page.locator("#report-output")).to_contain_text("路线图如何安排 PDF 和多知识库能力？")

    page.locator("#report-restore-button").click()
    expect(page.locator("#report-output")).to_contain_text("# RAG QA Bench 评测报告")


def test_audit_chunk_document_navigation_flow(live_server: str, browser_page) -> None:
    playwright = pytest.importorskip("playwright.sync_api")
    expect = playwright.expect
    page = browser_page

    page.goto(live_server, wait_until="networkidle")
    page.locator("#query").fill("系统支持哪些核心能力？")
    page.locator("#ask-button").click()

    expect(page.locator("#answer")).to_contain_text("审计 ID")
    expect(page.locator("#audit-output")).to_contain_text("检索候选")
    expect(page.locator("#chunk-output")).to_contain_text("当前片段正文")
    expect(page.locator("#document-output")).to_contain_text("分块时间线")
    expect(page.locator("#document-filter-input")).to_have_value("系统支持哪些核心能力？")
    expect(page.locator("#document-output")).to_contain_text("当前显示 0 / 2 个 chunk")

    page.locator("#document-filter-input").fill("平台核心能力")
    expect(page.locator("#document-output")).to_contain_text("命中：平台核心能力")

    page.locator("#audit-output .case-button").first.click()
    expect(page.locator("#chunk-output")).to_contain_text("相邻上下文")

    page.locator("#document-output .case-button").first.click()
    expect(page.locator("#chunk-output")).to_contain_text("当前片段正文")
