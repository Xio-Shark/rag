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


def _install_snapshot_style(page) -> None:
    page.evaluate(
        """
        () => {
          const styleId = 'visual-regression-normalized-style';
          if (document.getElementById(styleId)) {
            return;
          }

          const style = document.createElement('style');
          style.id = styleId;
          style.textContent = `
            [data-visual-normalized='true'],
            [data-visual-normalized='true'] * {
              font-family: "Courier New", "Liberation Mono", monospace !important;
              letter-spacing: 0 !important;
              text-shadow: none !important;
              caret-color: transparent !important;
            }

            [data-visual-normalized='true'] .section-text,
            [data-visual-normalized='true'] .card-lead,
            [data-visual-normalized='true'] .report-caption,
            [data-visual-normalized='true'] .mini,
            [data-visual-normalized='true'] .status,
            [data-visual-normalized='true'] pre {
              overflow: hidden !important;
            }

            [data-visual-normalized='true'] button {
              display: flex !important;
              align-items: center !important;
              justify-content: center !important;
            }
          `;
          document.head.appendChild(style);
        }
        """
    )


def _normalize_section_shell(page, section_index: int, label: str) -> None:
    _install_snapshot_style(page)
    page.evaluate(
        """
        ({ sectionIndex, label }) => {
          const section = document.querySelectorAll('.section-shell')[sectionIndex];
          if (!section) {
            return;
          }

          section.setAttribute('data-visual-normalized', 'true');
          const skeletonFill =
            'repeating-linear-gradient(180deg, rgba(16, 35, 29, 0.14) 0 10px, ' +
            'transparent 10px 18px)';

          const applySkeleton = (
            node,
            height,
            width = '100%',
            radius = '12px',
            background = skeletonFill
          ) => {
            if (!node) {
              return;
            }
            node.textContent = '';
            node.style.width = width;
            node.style.height = height;
            node.style.minHeight = height;
            node.style.overflow = 'hidden';
            node.style.borderRadius = radius;
            node.style.background = background;
            node.style.color = 'transparent';
            node.style.webkitTextFillColor = 'transparent';
          };

          applySkeleton(
            section.querySelector('.section-kicker'),
            '28px',
            '120px',
            '999px',
            'linear-gradient(180deg, rgba(16, 35, 29, 0.08), rgba(16, 35, 29, 0.08))'
          );
          applySkeleton(section.querySelector('.section-title'), '38px', '72%', '14px');
          applySkeleton(section.querySelector('.section-text'), '56px', '100%', '14px');

          section.querySelectorAll('.path-pill').forEach((node, index) => {
            applySkeleton(
              node,
              '30px',
              `${84 + (index % 2) * 12}px`,
              '999px',
              'linear-gradient(180deg, rgba(255, 255, 255, 0.92), rgba(255, 255, 255, 0.92))'
            );
          });

          section.querySelectorAll('.card-step').forEach((node, index) => {
            applySkeleton(
              node,
              '22px',
              `${42 + (index % 3) * 6}px`,
              '999px',
              'linear-gradient(180deg, rgba(11, 93, 75, 0.12), rgba(11, 93, 75, 0.12))'
            );
          });

          section.querySelectorAll('article.card h2').forEach((node, index) => {
            applySkeleton(node, '24px', `${58 + (index % 3) * 8}%`, '10px');
          });

          section.querySelectorAll('.card-lead').forEach((node, index) => {
            applySkeleton(node, `${50 + (index % 2) * 6}px`, '100%', '12px');
          });

          section.querySelectorAll('button').forEach((node, index) => {
            node.textContent = '';
            node.style.minHeight = '52px';
            node.style.lineHeight = '1.2';
            node.style.color = 'transparent';
            node.style.webkitTextFillColor = 'transparent';
          });

          section.querySelectorAll('select').forEach((node, index) => {
            const option = document.createElement('option');
            option.value = `normalized-${label}-${index + 1}`;
            option.textContent = '';
            node.replaceChildren(option);
            node.value = option.value;
            node.style.minHeight = '52px';
            node.style.lineHeight = '1.2';
            node.style.color = 'transparent';
            node.style.webkitTextFillColor = 'transparent';
          });

          section.querySelectorAll('input').forEach((node) => {
            node.value = '';
            node.placeholder = '';
            node.style.color = 'transparent';
            node.style.webkitTextFillColor = 'transparent';
          });

          section.querySelectorAll('textarea').forEach((node) => {
            node.value = '';
            node.placeholder = '';
            node.style.height = '112px';
            node.style.color = 'transparent';
            node.style.webkitTextFillColor = 'transparent';
          });

          section.querySelectorAll('button, input, select, textarea').forEach((node) => {
            node.blur();
          });
        }
        """,
        {"sectionIndex": section_index, "label": label},
    )


def _settle_snapshot(page) -> None:
    page.mouse.move(0, 0)
    page.evaluate(
        """
        () => new Promise((resolve) => {
          requestAnimationFrame(() => requestAnimationFrame(resolve));
        })
        """
    )


def _normalize_experiment_center(page) -> None:
    _normalize_section_shell(page, 1, "Experiment")
    page.evaluate(
        """
        () => {
          const section = document.querySelectorAll('.section-shell')[1];
          if (!section) {
            return;
          }
          const skeletonFill =
            'repeating-linear-gradient(180deg, rgba(16, 35, 29, 0.14) 0 10px, ' +
            'transparent 10px 18px)';

          const setBlock = (selector, height, width = '100%') => {
            const node = section.querySelector(selector);
            if (!node) {
              return;
            }
            node.textContent = '';
            node.style.width = width;
            node.style.height = height;
            node.style.minHeight = height;
            node.style.overflow = 'hidden';
            node.style.borderRadius = '12px';
            node.style.background = skeletonFill;
            node.style.color = 'transparent';
            node.style.webkitTextFillColor = 'transparent';
          };

          setBlock('#run-eval-output', '5.2em');
          setBlock('#eval-output', '6em');
          setBlock('#compare-output', '8.8em');
          setBlock('#snapshot-output', '6em');
          setBlock('#compare-detail-output', '9.2em');
          setBlock('#report-meta', '2.6em');
          setBlock('#report-outline-output', '5.8em');
          setBlock('#report-output', '14.2em');
          setBlock('#replay-context-output', '3.8em');
          setBlock('#replay-output', '7em');
          setBlock('#replay-compare-output', '6.6em');
          setBlock('#replay-history-output', '6em');

          const reportCaption = section.querySelector('.report-caption');
          if (reportCaption) {
            reportCaption.textContent = '';
            reportCaption.style.height = '3.8em';
            reportCaption.style.minHeight = '3.8em';
            reportCaption.style.borderRadius = '12px';
            reportCaption.style.background = skeletonFill;
          }

          const reportRestoreButton = section.querySelector('#report-restore-button');
          if (reportRestoreButton) {
            reportRestoreButton.textContent = '';
            reportRestoreButton.disabled = false;
          }

          const reportSummary = section.querySelector('.report-nav summary');
          if (reportSummary) {
            reportSummary.textContent = '';
            reportSummary.style.height = '22px';
            reportSummary.style.width = '120px';
            reportSummary.style.borderRadius = '10px';
            reportSummary.style.background =
              'linear-gradient(180deg, rgba(16, 35, 29, 0.12), rgba(16, 35, 29, 0.12))';
          }

          section.querySelectorAll('details').forEach((node) => {
            node.open = true;
          });
        }
        """
    )
    _settle_snapshot(page)


def _prepare_qa_evidence_state(page, expect) -> None:
    page.locator("#query").fill("系统支持哪些核心能力？")
    page.locator("#ask-button").click()
    expect(page.locator("#answer")).to_contain_text("审计 ID")
    expect(page.locator("#audit-output")).to_contain_text("检索候选")
    expect(page.locator("#chunk-output")).to_contain_text("当前片段正文")
    expect(page.locator("#document-output")).to_contain_text("分块时间线")


def _normalize_qa_evidence_sections(page) -> None:
    _normalize_section_shell(page, 0, "QA")
    _normalize_section_shell(page, 2, "Evidence")
    page.evaluate(
        """
        () => {
          const qaSection = document.querySelectorAll('.section-shell')[0];
          const evidenceSection = document.querySelectorAll('.section-shell')[2];
          if (!qaSection || !evidenceSection) {
            return;
          }
          const skeletonFill =
            'repeating-linear-gradient(180deg, rgba(16, 35, 29, 0.14) 0 10px, ' +
            'transparent 10px 18px)';

          const qaCards = qaSection.querySelectorAll('.grid > .card');
          qaCards.forEach((card, index) => {
            if (index === 1 || index === 2) {
              card.style.display = 'none';
            }
          });

          const setBlock = (root, selector, height, width = '100%') => {
            const node = root.querySelector(selector);
            if (!node) {
              return;
            }
            node.textContent = '';
            node.style.width = width;
            node.style.height = height;
            node.style.minHeight = height;
            node.style.overflow = 'hidden';
            node.style.borderRadius = '12px';
            node.style.background = skeletonFill;
            node.style.color = 'transparent';
            node.style.webkitTextFillColor = 'transparent';
          };

          setBlock(qaSection, '#answer', '10.4em');
          setBlock(qaSection, '#audit-output', '9em');
          setBlock(qaSection, '#audit-list-output', '6em');
          setBlock(evidenceSection, '#chunk-output', '10.4em');
          setBlock(evidenceSection, '#document-output', '12.6em');
        }
        """
    )
    _settle_snapshot(page)


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
    _install_snapshot_style(page)
    page.evaluate(
        """
        () => {
          const reportCard = document.querySelector('article.card.card-sticky');
          if (!reportCard) {
            return;
          }

          reportCard.setAttribute('data-visual-normalized', 'true');
          const skeletonFill =
            'repeating-linear-gradient(180deg, rgba(16, 35, 29, 0.14) 0 10px, ' +
            'transparent 10px 18px)';

          const cardStep = reportCard.querySelector('.card-step');
          if (cardStep) {
            cardStep.textContent = '10';
          }

          const cardTitle = reportCard.querySelector('h2');
          if (cardTitle) {
            cardTitle.textContent = '';
            cardTitle.style.width = '58%';
            cardTitle.style.height = '24px';
            cardTitle.style.borderRadius = '10px';
            cardTitle.style.background = skeletonFill;
          }

          const reportLead = reportCard.querySelector('.card-lead');
          if (reportLead) {
            reportLead.textContent = '';
            reportLead.style.height = '54px';
            reportLead.style.minHeight = '54px';
            reportLead.style.borderRadius = '12px';
            reportLead.style.background = skeletonFill;
          }

          const reportRunSelect = document.getElementById('report-run-select');
          if (reportRunSelect) {
            const option = document.createElement('option');
            option.value = 'normalized-run';
            option.textContent = '';
            reportRunSelect.replaceChildren(option);
            reportRunSelect.value = option.value;
            reportRunSelect.style.minHeight = '52px';
            reportRunSelect.style.lineHeight = '1.2';
            reportRunSelect.style.color = 'transparent';
            reportRunSelect.style.webkitTextFillColor = 'transparent';
          }

          const reportMeta = document.getElementById('report-meta');
          if (reportMeta) {
            reportMeta.textContent = '';
            reportMeta.style.height = '2.6em';
            reportMeta.style.minHeight = '2.6em';
            reportMeta.style.borderRadius = '10px';
            reportMeta.style.background = skeletonFill;
          }

          const reportFormatSelect = document.getElementById('report-format-select');
          if (reportFormatSelect) {
            const option = document.createElement('option');
            option.value = 'markdown';
            option.textContent = '';
            reportFormatSelect.replaceChildren(option);
            reportFormatSelect.value = option.value;
            reportFormatSelect.style.minHeight = '52px';
            reportFormatSelect.style.lineHeight = '1.2';
            reportFormatSelect.style.color = 'transparent';
            reportFormatSelect.style.webkitTextFillColor = 'transparent';
          }

          const reportButton = document.getElementById('report-button');
          if (reportButton) {
            reportButton.textContent = '';
            reportButton.style.display = 'flex';
            reportButton.style.alignItems = 'center';
            reportButton.style.justifyContent = 'center';
            reportButton.style.minHeight = '52px';
            reportButton.style.lineHeight = '1.2';
          }

          const reportRestoreButton = document.getElementById('report-restore-button');
          if (reportRestoreButton) {
            reportRestoreButton.textContent = '';
            reportRestoreButton.disabled = false;
          }

          const reportSummary = reportCard.querySelector('.report-nav summary');
          if (reportSummary) {
            reportSummary.textContent = '';
            reportSummary.style.height = '22px';
            reportSummary.style.width = '120px';
            reportSummary.style.borderRadius = '10px';
            reportSummary.style.background =
              'linear-gradient(180deg, rgba(16, 35, 29, 0.12), rgba(16, 35, 29, 0.12))';
          }

          const reportCaption = reportCard.querySelector('.report-caption');
          if (reportCaption) {
            reportCaption.textContent = '';
            reportCaption.style.height = '3.8em';
            reportCaption.style.minHeight = '3.8em';
            reportCaption.style.borderRadius = '12px';
            reportCaption.style.background = skeletonFill;
          }

          const reportOutline = document.getElementById('report-outline-output');
          if (reportOutline) {
            reportOutline.textContent = '';
            reportOutline.style.height = '5.8em';
            reportOutline.style.minHeight = '5.8em';
            reportOutline.style.borderRadius = '12px';
            reportOutline.style.background = skeletonFill;
          }

          const reportOutput = document.getElementById('report-output');
          if (reportOutput) {
            reportOutput.textContent = '';
            reportOutput.style.height = '14.2em';
            reportOutput.style.minHeight = '14.2em';
            reportOutput.style.borderRadius = '12px';
            reportOutput.style.background = skeletonFill;
          }

          reportCard.querySelectorAll('details').forEach((node) => {
            node.open = true;
          });

          reportCard.querySelectorAll('button, input, select, textarea').forEach((node) => {
            node.blur();
          });
        }
        """
    )
    _settle_snapshot(page)


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
