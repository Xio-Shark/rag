from __future__ import annotations

import argparse
import html
import re
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, StyleSheet1
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer

DEFAULT_SOURCES = [
    Path("/Users/xioshark/Desktop/career/滕彦翕-AI应用工程与平台工具实习简历.md"),
    Path("/Users/xioshark/Desktop/career/滕彦翕-SRE运维开发实习简历.md"),
    Path("/Users/xioshark/Desktop/career/滕彦翕-后端平台研发实习简历.md"),
    Path("/Users/xioshark/Desktop/career/滕彦翕-测试开发与质量平台实习简历.md"),
]
DEFAULT_OUTPUT_DIR = Path("/Users/xioshark/Desktop/career/output/pdf")

LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
CODE_RE = re.compile(r"`([^`]+)`")


def register_fonts() -> None:
    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    pdfmetrics.registerFont(
        TTFont(
            "STHeiti-Medium",
            "/System/Library/Fonts/STHeiti Medium.ttc",
            subfontIndex=0,
        )
    )


def make_styles() -> StyleSheet1:
    styles = StyleSheet1()
    styles.add(
        ParagraphStyle(
            name="Name",
            fontName="STHeiti-Medium",
            fontSize=20,
            leading=24,
            textColor=colors.HexColor("#10231d"),
            alignment=TA_CENTER,
            spaceAfter=5,
            wordWrap="CJK",
        )
    )
    styles.add(
        ParagraphStyle(
            name="Contact",
            fontName="STSong-Light",
            fontSize=9.5,
            leading=13,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#33423e"),
            spaceAfter=5,
            wordWrap="CJK",
        )
    )
    styles.add(
        ParagraphStyle(
            name="Summary",
            fontName="STSong-Light",
            fontSize=9.8,
            leading=14,
            alignment=TA_LEFT,
            textColor=colors.HexColor("#10231d"),
            spaceAfter=6,
            wordWrap="CJK",
        )
    )
    styles.add(
        ParagraphStyle(
            name="Section",
            fontName="STSong-Light",
            fontSize=12,
            leading=16,
            textColor=colors.HexColor("#0b5d4b"),
            spaceBefore=6,
            spaceAfter=4,
            wordWrap="CJK",
        )
    )
    styles.add(
        ParagraphStyle(
            name="Project",
            fontName="STSong-Light",
            fontSize=10.8,
            leading=14,
            textColor=colors.HexColor("#10231d"),
            spaceBefore=6,
            spaceAfter=3,
            wordWrap="CJK",
        )
    )
    styles.add(
        ParagraphStyle(
            name="Body",
            fontName="STSong-Light",
            fontSize=9.4,
            leading=13.4,
            textColor=colors.HexColor("#10231d"),
            spaceAfter=4,
            wordWrap="CJK",
        )
    )
    styles.add(
        ParagraphStyle(
            name="Bullet",
            parent=styles["Body"],
            leftIndent=12,
            firstLineIndent=0,
            bulletIndent=0,
            spaceAfter=3,
        )
    )
    return styles


def inline_markup(text: str) -> str:
    escaped = html.escape(text.strip())
    escaped = LINK_RE.sub(
        lambda match: (
            f'<font color="#0b5d4b"><u><a href="{html.escape(match.group(2), quote=True)}">'
            f"{html.escape(match.group(1))}</a></u></font>"
        ),
        escaped,
    )
    escaped = BOLD_RE.sub(lambda match: f"<b>{html.escape(match.group(1))}</b>", escaped)
    escaped = CODE_RE.sub(
        lambda match: f'<font color="#0b5d4b">{html.escape(match.group(1))}</font>',
        escaped,
    )
    return escaped.replace("  ", "<br/>")


def build_story(source: Path, styles: StyleSheet1) -> list:
    lines = source.read_text(encoding="utf-8").splitlines()
    story: list = []
    paragraph_buffer: list[str] = []
    top_block_index = [0]

    def flush_with_context() -> None:
        if not paragraph_buffer:
            return
        text = "<br/>".join(
            inline_markup(line.rstrip()) for line in paragraph_buffer if line.strip()
        )
        if not text:
            paragraph_buffer.clear()
            return
        if top_block_index[0] == 0:
            style = styles["Contact"]
        elif top_block_index[0] == 1:
            style = styles["Summary"]
        else:
            style = styles["Body"]
        story.append(Paragraph(text, style))
        paragraph_buffer.clear()
        top_block_index[0] += 1

    for raw_line in lines:
        line = raw_line.rstrip()
        if not line.strip():
            flush_with_context()
            continue
        if line.strip() == "---":
            flush_with_context()
            story.append(Spacer(1, 2))
            story.append(
                HRFlowable(
                    width="100%",
                    thickness=0.4,
                    color=colors.HexColor("#c9d6d1"),
                )
            )
            story.append(Spacer(1, 3))
            continue
        if line.startswith("# "):
            flush_with_context()
            story.append(Paragraph(inline_markup(line[2:]), styles["Name"]))
            continue
        if line.startswith("## "):
            flush_with_context()
            story.append(Paragraph(inline_markup(line[3:]), styles["Section"]))
            continue
        if line.startswith("### "):
            flush_with_context()
            story.append(Paragraph(inline_markup(line[4:]), styles["Project"]))
            continue
        if line.startswith("- "):
            flush_with_context()
            story.append(
                Paragraph(
                    inline_markup(line[2:]),
                    styles["Bullet"],
                    bulletText="•",
                )
            )
            continue
        paragraph_buffer.append(line)

    flush_with_context()
    return story


def export_pdf(source: Path, output_dir: Path, styles: StyleSheet1) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{source.stem}.pdf"
    document = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
        title=source.stem,
        author="Xio-Shark",
    )
    document.build(build_story(source, styles))
    return output_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="把 Markdown 简历导出为 PDF")
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="PDF 输出目录",
    )
    parser.add_argument(
        "sources",
        nargs="*",
        help="待导出的 Markdown 文件，默认导出 4 份岗位简历",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    register_fonts()
    styles = make_styles()
    sources = [Path(item) for item in args.sources] if args.sources else DEFAULT_SOURCES
    output_dir = Path(args.output_dir)

    for source in sources:
        output_path = export_pdf(source=source, output_dir=output_dir, styles=styles)
        print(output_path)


if __name__ == "__main__":
    main()
