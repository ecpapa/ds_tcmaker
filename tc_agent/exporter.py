"""TestSuite를 Markdown 리포트([image_analysis] 태그 포함)와 엑셀 TC 시트로 저장한다."""

from __future__ import annotations

import json
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill

from .schema import TestSuite

TC_COLUMNS = [
    ("tc_id", "TC ID", 10),
    ("category", "분류", 18),
    ("title", "테스트 항목", 30),
    ("case_type", "유형", 10),
    ("priority", "우선순위", 9),
    ("test_path", "테스트 경로", 30),
    ("precondition", "사전 조건", 30),
    ("steps", "수행 동작", 50),
    ("expected_result", "기대 결과", 50),
    ("source", "근거", 20),
]


def _cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", "<br>")


def to_markdown(suite: TestSuite, title: str) -> str:
    a = suite.analysis
    out = [f"# {title} 테스트 케이스", "", "[image_analysis]", "", "## 1. Technical Logic Analysis", ""]
    out += [f"- **Domain Definition**: {a.domain}", f"- **Core Objective**: {a.core_objective}", ""]
    out += ["### Technical-to-Business Mapping", "", "| 기술 변수 | 비즈니스 의미 |", "|---|---|"]
    out += [f"| {_cell(m.technical_variable)} | {_cell(m.business_meaning)} |" for m in a.mappings]
    out += ["", "### Logic Summary", ""] + [f"- {s}" for s in a.logic_summary]
    out += ["", "## 2. Test Case Structure Analysis", "", "### Test Objective", ""]
    out += [f"- {s}" for s in a.test_objectives]
    out += ["", "### Categorization & Path", "", "| 테스트 그룹 | 진입 경로 |", "|---|---|"]
    out += [f"| {_cell(c.name)} | {_cell(c.entry_point)} |" for c in a.categories]
    out += ["", "[/image_analysis]", ""]

    positive = sum(tc.case_type == "Positive" for tc in suite.test_cases)
    out += [
        "## Test Case [Step-by-Step]",
        "",
        f"총 {len(suite.test_cases)}건 (Positive {positive} / Negative {len(suite.test_cases) - positive})",
        "",
        "| " + " | ".join(h for _, h, _ in TC_COLUMNS) + " |",
        "|" + "---|" * len(TC_COLUMNS),
    ]
    for tc in suite.test_cases:
        out.append("| " + " | ".join(_cell(str(getattr(tc, k))) for k, _, _ in TC_COLUMNS) + " |")

    if suite.open_questions:
        out += ["", "## 기획 확인 필요 사항", ""] + [f"- [ ] {q}" for q in suite.open_questions]
    return "\n".join(out) + "\n"


def to_excel(suite: TestSuite, path: Path) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "TestCases"
    header_fill = PatternFill("solid", fgColor="1F4E78")
    for col, (_, header, width) in enumerate(TC_COLUMNS, start=1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center")
        ws.column_dimensions[cell.column_letter].width = width
    # 실행 결과를 적을 수 있게 빈 칸을 둔다
    for extra, width in (("결과(P/F)", 10), ("비고", 25)):
        cell = ws.cell(row=1, column=ws.max_column + 1, value=extra)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = header_fill
        ws.column_dimensions[cell.column_letter].width = width

    wrap = Alignment(wrap_text=True, vertical="top")
    for row, tc in enumerate(suite.test_cases, start=2):
        for col, (key, _, _) in enumerate(TC_COLUMNS, start=1):
            ws.cell(row=row, column=col, value=str(getattr(tc, key))).alignment = wrap
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions

    if suite.open_questions:
        qs = wb.create_sheet("기획확인필요")
        qs.append(["No", "확인 사항", "답변"])
        qs.column_dimensions["B"].width = 80
        qs.column_dimensions["C"].width = 40
        for i, q in enumerate(suite.open_questions, start=1):
            qs.append([i, q, ""])
    wb.save(path)


def save_all(suite: TestSuite, out_dir: Path, title: str) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    md = out_dir / "test_cases.md"
    xlsx = out_dir / "test_cases.xlsx"
    raw = out_dir / "result.json"
    md.write_text(to_markdown(suite, title), encoding="utf-8")
    to_excel(suite, xlsx)
    raw.write_text(json.dumps(suite.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")
    return [md, xlsx, raw]
