from __future__ import annotations

import socket
import threading
import time
from pathlib import Path
from typing import Generator

import httpx
import pytest
import uvicorn

from tests.visual_regression import assert_visual_match, stack_images_vertically

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
        page = browser.new_page(viewport={"width": 1440, "height": 2200}, device_scale_factor=1)
        try:
            yield page
        finally:
            browser.close()


@pytest.fixture()
def mobile_browser_page() -> Generator[object, None, None]:
    playwright = pytest.importorskip("playwright.sync_api")
    with playwright.sync_playwright() as runner:
        try:
            browser = runner.chromium.launch()
        except Exception as exc:  # pragma: no cover
            pytest.skip(f"Chromium 不可用，跳过 E2E：{exc}")
        page = browser.new_page(
            viewport={"width": 430, "height": 2400},
            device_scale_factor=1,
            is_mobile=True,
            has_touch=True,
        )
        try:
            yield page
        finally:
            browser.close()


@pytest.fixture()
def tablet_browser_page() -> Generator[object, None, None]:
    playwright = pytest.importorskip("playwright.sync_api")
    with playwright.sync_playwright() as runner:
        try:
            browser = runner.chromium.launch()
        except Exception as exc:  # pragma: no cover
            pytest.skip(f"Chromium 不可用，跳过 E2E：{exc}")
        page = browser.new_page(
            viewport={"width": 900, "height": 2400},
            device_scale_factor=1,
            has_touch=True,
        )
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


def _prepare_visual_state(page, expect) -> None:
    _prepare_compare_runs(page, expect)
    expect(page.locator("#compare-output")).to_contain_text("建议动作")
    page.locator("#compare-output [data-summary-action='focus-case']").click()
    expect(page.locator("#compare-detail-output")).to_contain_text("路线图双事实")
    expect(page.locator("#report-output")).to_contain_text("路线图双事实")


def _normalize_experiment_center(page) -> None:
    page.evaluate(
        """
        () => {
          const section = document.querySelectorAll('.section-shell')[1];
          if (!section) {
            return;
          }

          const replacePatterns = [
            [/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/gi, '<id>'],
            [/\\b\\d{4}-\\d{2}-\\d{2}[ T]\\d{2}:\\d{2}:\\d{2}(?:\\.\\d+)?\\b/g, '<time>'],
            [/\\/[^\\s]+\\/report\\.(?:md|json)/g, '<report-path>'],
            [
              /latency_p95_ms[\\s\\S]*?unchanged/g,
              'latency_p95_ms\\n<metric>\\n<baseline>\\n<delta>\\nunchanged'
            ],
          ];

          const walker = document.createTreeWalker(section, NodeFilter.SHOW_TEXT);
          while (walker.nextNode()) {
            let value = walker.currentNode.nodeValue || '';
            replacePatterns.forEach(([pattern, replacement]) => {
              value = value.replace(pattern, replacement);
            });
            walker.currentNode.nodeValue = value;
          }

          section.querySelectorAll('button, input, select, textarea').forEach((node) => {
            node.blur();
          });
        }
        """
    )


def _prepare_qa_evidence_state(page, expect) -> None:
    page.locator("#query").fill("系统支持哪些核心能力？")
    page.locator("#ask-button").click()
    expect(page.locator("#answer")).to_contain_text("审计 ID")
    expect(page.locator("#audit-output")).to_contain_text("检索候选")
    expect(page.locator("#chunk-output")).to_contain_text("当前片段正文")
    expect(page.locator("#document-output")).to_contain_text("分块时间线")


def _normalize_qa_evidence_sections(page) -> None:
    page.evaluate(
        """
        () => {
          const qaSection = document.querySelectorAll('.section-shell')[0];
          const evidenceSection = document.querySelectorAll('.section-shell')[2];
          if (!qaSection || !evidenceSection) {
            return;
          }

          const qaCards = qaSection.querySelectorAll('.grid > .card');
          qaCards.forEach((card, index) => {
            if (index === 1 || index === 2) {
              card.style.display = 'none';
            }
          });

          const replacePatterns = [
            [/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/gi, '<id>'],
            [/\\/private\\/var\\/folders\\/[^\\s]+/g, '<source-path>'],
            [/\\b\\d+\\.\\d+ ms\\b/g, '<latency> ms'],
          ];

          [qaSection, evidenceSection].forEach((section) => {
            const walker = document.createTreeWalker(section, NodeFilter.SHOW_TEXT);
            while (walker.nextNode()) {
              let value = walker.currentNode.nodeValue || '';
              replacePatterns.forEach(([pattern, replacement]) => {
                value = value.replace(pattern, replacement);
              });
              walker.currentNode.nodeValue = value;
            }

            section.querySelectorAll('button, input, select, textarea').forEach((node) => {
              node.blur();
            });
          });
        }
        """
    )


def _prepare_report_panel_state(page, expect) -> None:
    _, target_run_id = _prepare_compare_runs(page, expect)
    page.select_option("#report-run-select", value=target_run_id)
    page.select_option("#report-format-select", value="markdown")
    page.locator("#report-button").click()
    expect(page.locator("#report-meta")).to_contain_text("report.md")
    expect(page.locator("#report-outline-output")).to_contain_text("路线图双事实")
    page.locator("#report-outline-output .outline-button", has_text="路线图双事实").click()
    expect(page.locator("#report-meta")).to_contain_text("已定位到 路线图双事实")
    expect(page.locator("#report-output")).to_contain_text("路线图如何安排 PDF 和多知识库能力？")
    expect(page.locator("#report-restore-button")).to_be_enabled()


def _normalize_report_panel(page) -> None:
    page.evaluate(
        """
        () => {
          const reportCard = document.querySelector('article.card.card-sticky');
          if (!reportCard) {
            return;
          }

          const reportLead = reportCard.querySelector('.card-lead');
          if (reportLead) {
            reportLead.innerHTML =
              '报告面板归一化后保留正文、导航与恢复操作。<br>顶部说明文案固定，避免换行抖动。';
            reportLead.style.minHeight = '3.3em';
          }

          const reportRunSelect = document.getElementById('report-run-select');
          if (reportRunSelect) {
            const option = document.createElement('option');
            option.value = 'normalized-run';
            option.textContent = 'compact_context | <time> | <id>';
            reportRunSelect.replaceChildren(option);
            reportRunSelect.value = option.value;
            reportRunSelect.style.minHeight = '52px';
            reportRunSelect.style.lineHeight = '1.2';
          }

          const reportMeta = document.getElementById('report-meta');
          if (reportMeta) {
            reportMeta.textContent = '<report-path> | 已定位到 路线图双事实';
            reportMeta.style.minHeight = '24px';
          }

          const reportFormatSelect = document.getElementById('report-format-select');
          if (reportFormatSelect) {
            const option = document.createElement('option');
            option.value = 'markdown';
            option.textContent = 'Markdown';
            reportFormatSelect.replaceChildren(option);
            reportFormatSelect.value = option.value;
            reportFormatSelect.style.minHeight = '52px';
            reportFormatSelect.style.lineHeight = '1.2';
          }

          const reportButton = document.getElementById('report-button');
          if (reportButton) {
            reportButton.textContent = '读取报告正文';
            reportButton.style.display = 'flex';
            reportButton.style.alignItems = 'center';
            reportButton.style.justifyContent = 'center';
            reportButton.style.minHeight = '52px';
            reportButton.style.lineHeight = '1.2';
          }

          const replacePatterns = [
            [/\\/[^\\n|]+report\\.(?:md|json)/g, '<report-path>'],
            [/\\b\\d{4}-\\d{2}-\\d{2}[ T]\\d{2}:\\d{2}:\\d{2}(?:\\.\\d+)?\\b/g, '<time>'],
            [/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/gi, '<id>'],
          ];

          const walker = document.createTreeWalker(reportCard, NodeFilter.SHOW_TEXT);
          while (walker.nextNode()) {
            let value = walker.currentNode.nodeValue || '';
            replacePatterns.forEach(([pattern, replacement]) => {
              value = value.replace(pattern, replacement);
            });
            walker.currentNode.nodeValue = value;
          }

          reportCard.querySelectorAll('button, input, select, textarea').forEach((node) => {
            node.blur();
          });
        }
        """
    )
    page.mouse.move(0, 0)
    page.evaluate(
        """
        () => new Promise((resolve) => {
          requestAnimationFrame(() => requestAnimationFrame(resolve));
        })
        """
    )


def test_experiment_center_visual_regression(live_server: str, browser_page) -> None:
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

    _prepare_visual_state(page, expect)
    _normalize_experiment_center(page)

    section = page.locator(".section-shell").nth(1)
    image_bytes = section.screenshot(animations="disabled")
    assert_visual_match(
        image_bytes,
        Path(__file__).parent / "baselines" / "experiment-center.png",
    )


def test_qa_and_evidence_visual_regression(live_server: str, browser_page) -> None:
    playwright = pytest.importorskip("playwright.sync_api")
    expect = playwright.expect
    page = browser_page

    page.goto(live_server, wait_until="networkidle")
    _prepare_qa_evidence_state(page, expect)
    _normalize_qa_evidence_sections(page)

    qa_section_image = page.locator(".section-shell").nth(0).screenshot(animations="disabled")
    evidence_section_image = page.locator(".section-shell").nth(2).screenshot(animations="disabled")
    combined_image = stack_images_vertically([qa_section_image, evidence_section_image], gap=24)

    assert_visual_match(
        combined_image,
        Path(__file__).parent / "baselines" / "qa-evidence-workflow.png",
    )


def test_report_panel_visual_regression(live_server: str, browser_page) -> None:
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

    _prepare_report_panel_state(page, expect)
    _normalize_report_panel(page)

    report_card = page.locator("article.card.card-sticky").first
    image_bytes = report_card.screenshot(animations="disabled")
    assert_visual_match(
        image_bytes,
        Path(__file__).parent / "baselines" / "report-panel.png",
    )


def test_mobile_experiment_center_visual_regression(
    live_server: str, mobile_browser_page
) -> None:
    playwright = pytest.importorskip("playwright.sync_api")
    expect = playwright.expect
    page = mobile_browser_page

    page.goto(live_server, wait_until="networkidle")
    page.wait_for_function(
        "document.querySelector('#dataset-select').options.length > 1"
    )
    page.wait_for_function(
        "document.querySelector('#snapshot-select').options.length > 1"
    )

    _prepare_visual_state(page, expect)
    _normalize_experiment_center(page)

    section = page.locator(".section-shell").nth(1)
    image_bytes = section.screenshot(animations="disabled")
    assert_visual_match(
        image_bytes,
        Path(__file__).parent / "baselines" / "mobile-experiment-center.png",
    )


def test_tablet_qa_and_evidence_visual_regression(
    live_server: str, tablet_browser_page
) -> None:
    playwright = pytest.importorskip("playwright.sync_api")
    expect = playwright.expect
    page = tablet_browser_page

    page.goto(live_server, wait_until="networkidle")
    _prepare_qa_evidence_state(page, expect)
    _normalize_qa_evidence_sections(page)

    qa_section_image = page.locator(".section-shell").nth(0).screenshot(animations="disabled")
    evidence_section_image = page.locator(".section-shell").nth(2).screenshot(animations="disabled")
    combined_image = stack_images_vertically([qa_section_image, evidence_section_image], gap=24)

    assert_visual_match(
        combined_image,
        Path(__file__).parent / "baselines" / "tablet-qa-evidence-workflow.png",
    )


def test_tablet_report_panel_visual_regression(
    live_server: str, tablet_browser_page
) -> None:
    playwright = pytest.importorskip("playwright.sync_api")
    expect = playwright.expect
    page = tablet_browser_page

    page.goto(live_server, wait_until="networkidle")
    page.wait_for_function(
        "document.querySelector('#dataset-select').options.length > 1"
    )
    page.wait_for_function(
        "document.querySelector('#snapshot-select').options.length > 1"
    )

    _prepare_report_panel_state(page, expect)
    _normalize_report_panel(page)

    report_card = page.locator("article.card.card-sticky").first
    image_bytes = report_card.screenshot(animations="disabled")
    assert_visual_match(
        image_bytes,
        Path(__file__).parent / "baselines" / "tablet-report-panel.png",
    )
