"""KLAS section-layout regressions with entirely fictional course history."""

from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import Table, TableStyle

from app.main import app
from app.services.transcript_parser import TranscriptParseError, parse_transcript
from tests.test_transcript_parser import COURSE, HEADERS, mock_pages, parse_rows

KLAS_HEADERS = ["과목명", "이수구분", "학점", "성적", "재수강여부"]


def section(title):
    return [title, None, None, None, None]


def _draw_table(document, rows, *, top):
    table = Table(rows, colWidths=[140] * 5, rowHeights=[22] * len(rows))
    styles = [
        ("FONTNAME", (0, 0), (-1, -1), "HYSMyeongJo-Medium"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("GRID", (0, 0), (-1, -1), 0.6, colors.black),
    ]
    for index, row in enumerate(rows):
        if row[0] and all(value is None for value in row[1:]):
            styles.append(("SPAN", (0, index), (-1, index)))
    table.setStyle(TableStyle(styles))
    table.wrapOn(document, 800, 900)
    table.drawOn(document, 30, top - 22 * len(rows))


def make_sectioned_pdf(pages):
    """Draw real PDF grids, merged semester cells and page breaks in memory."""
    pdfmetrics.registerFont(UnicodeCIDFont("HYSMyeongJo-Medium"))
    stream = BytesIO()
    document = Canvas(stream, pagesize=(900, 1000))
    for index, tables in enumerate(pages):
        document.setFont("HYSMyeongJo-Medium", 10)
        document.drawString(30, 970, f"Synthetic transcript page {index + 1}")
        for table_index, rows in enumerate(tables):
            _draw_table(document, rows, top=920 - table_index * 550)
        document.showPage()
    document.save()
    return stream.getvalue()


def synthetic_45_rows():
    """Invented years, names, grades and group sizes; never a private fixture."""
    groups = [
        (2031, "2", "2031학년도 2학기", 8),
        (2031, "summer", "2031학년도 계절학기(하계)", 4),
        (2031, "1", "2031학년도 1학기", 6),
        (2030, "winter", "2030학년도 계절학기(동계)", 3),
        (2030, "2", "2030학년도 2학기", 5),
        (2030, "1", "2030학년도 1학기", 5),
        (2029, "2", "2029학년도 2학기", 7),
        (2029, "1", "2029학년도 1학기", 7),
    ]
    pages = []
    expected = []
    page_rows = []
    page_courses = 0
    index = 0
    for year, term, title, count in groups:
        page_rows.extend([section(title), KLAS_HEADERS.copy()])
        for _ in range(count):
            if page_courses == 15:
                pages.append([page_rows])
                page_rows = [section(title), KLAS_HEADERS.copy()]
                page_courses = 0
            grade = None if index < 5 else "B+"
            if index in {12, 18, 27}:
                grade = "D+(삭제)"
            elif index == 9:
                grade = "F"
            elif index == 10:
                grade = "NP"
            elif index == 30:
                grade = "P"
            retake = index in {4, 8, 12, 34}
            category = "전필" if index % 2 else "교선"
            credits = 1.5 if index == 20 else 3
            name = f"가상과목{index + 1:03d}"
            page_rows.append(
                [name, category, str(credits), grade or "", "재수강" if retake else ""]
            )
            expected.append(
                {
                    "year": year,
                    "term": term,
                    "course_code": None,
                    "name": name,
                    "category": category,
                    "credits": credits,
                    "grade": grade,
                    "is_retake": retake,
                }
            )
            page_courses += 1
            index += 1
    pages.append([page_rows])
    return pages, expected


def test_real_generated_three_page_pdf_preserves_all_45_rows():
    pages, expected = synthetic_45_rows()
    result = parse_transcript(make_sectioned_pdf(pages))
    assert len(pages) == 3
    assert [course.model_dump() for course in result.courses] == expected
    assert len(result.courses) == 45
    assert result.parse_warnings == []
    assert result.admission_year is None


def test_sectioned_45_row_pdf_parses_through_api():
    pages, expected = synthetic_45_rows()
    response = TestClient(app).post(
        "/transcripts/parse",
        files={"file": ("synthetic.pdf", make_sectioned_pdf(pages), "application/pdf")},
    )
    assert response.status_code == 200
    assert response.json()["courses"] == expected
    assert response.json()["parse_warnings"] == []


@pytest.mark.parametrize(
    ("title", "year", "term"),
    [
        ("2031학년도 1학기", 2031, "1"),
        ("2031학년도 2학기", 2031, "2"),
        ("2030학년도 계절학기(하계)", 2030, "summer"),
        ("2030학년도 계절학기(동계)", 2030, "winter"),
    ],
)
def test_semester_sections_apply_to_following_courses(monkeypatch, title, year, term):
    mock_pages(
        monkeypatch,
        [("Synthetic", [[section(title), KLAS_HEADERS, ["가상가", "전선", "2", "A0", ""]]])],
    )
    result = parse_transcript(b"%PDF-synthetic mock")
    assert (result.courses[0].year, result.courses[0].term) == (year, term)
    assert result.courses[0].course_code is None
    assert result.parse_warnings == []


def test_repeated_semester_headers_across_pages_do_not_deduplicate_attempts(monkeypatch):
    rows = [section("2031학년도 1학기"), KLAS_HEADERS, ["가상반복", "전선", "3", "F", ""]]
    mock_pages(monkeypatch, [("Synthetic first", [rows]), ("Synthetic second", [rows])])
    result = parse_transcript(b"%PDF-synthetic mock")
    assert len(result.courses) == 2
    assert result.courses[0] == result.courses[1]
    assert result.parse_warnings == []


def test_headerless_matching_page_continuation_uses_confirmed_section(monkeypatch):
    mock_pages(
        monkeypatch,
        [
            (
                "Synthetic first",
                [
                    [
                        section("2031학년도 2학기"),
                        KLAS_HEADERS,
                        ["가상가", "전선", "3", "", "재수강"],
                    ]
                ],
            ),
            ("Synthetic second", [[["가상나", "교선", "1.5", "P", ""]]]),
        ],
    )
    result = parse_transcript(b"%PDF-synthetic mock")
    assert [(course.year, course.term) for course in result.courses] == [(2031, "2"), (2031, "2")]
    assert [course.name for course in result.courses] == ["가상가", "가상나"]
    assert result.parse_warnings == []


def test_five_column_header_without_semester_context_is_not_guessed(monkeypatch):
    mock_pages(monkeypatch, [("Synthetic", [[KLAS_HEADERS, ["가상가", "전선", "3", "A0", ""]]])])
    with pytest.raises(TranscriptParseError) as error:
        parse_transcript(b"%PDF-synthetic mock")
    assert error.value.code == "TABLE_NOT_FOUND"


@pytest.mark.parametrize(
    ("grade", "marker", "expected_grade", "is_retake"),
    [
        ("", "", None, False),
        (None, "재수강", None, True),
        ("C+(삭제)", "", "C+(삭제)", False),
        ("D+(삭제)", "재수강", "D+(삭제)", True),
        ("F", "", "F", False),
        ("NP", "", "NP", False),
    ],
)
def test_blank_deleted_and_failed_grades_are_preserved_independently(
    monkeypatch, grade, marker, expected_grade, is_retake
):
    mock_pages(
        monkeypatch,
        [
            (
                "Synthetic",
                [
                    [
                        section("2030학년도 1학기"),
                        KLAS_HEADERS,
                        ["가상가", "전선", "3", grade, marker],
                    ]
                ],
            )
        ],
    )
    course = parse_transcript(b"%PDF-synthetic mock").courses[0]
    assert course.grade == expected_grade
    assert course.is_retake is is_retake


def test_explicit_column_adapter_also_preserves_blank_grade_as_null(monkeypatch):
    row = COURSE.copy()
    row[6] = ""
    result = parse_rows(monkeypatch, [HEADERS, row])
    assert len(result.courses) == 1
    assert result.courses[0].grade is None
    assert result.parse_warnings == []


def test_invalid_course_row_warns_without_dropping_following_valid_row(monkeypatch):
    mock_pages(
        monkeypatch,
        [
            (
                "Synthetic",
                [
                    [
                        section("2031학년도 1학기"),
                        KLAS_HEADERS,
                        ["가상가", "전선", "not-numeric", "B0", ""],
                        ["가상나", "교선", "2", "P", ""],
                    ]
                ],
            )
        ],
    )
    result = parse_transcript(b"%PDF-synthetic mock")
    assert [course.name for course in result.courses] == ["가상나"]
    assert [warning.row for warning in result.parse_warnings] == [3]
    assert "not-numeric" not in result.model_dump_json()


def test_student_and_summary_tables_are_not_course_rows_or_warnings(monkeypatch):
    mock_pages(
        monkeypatch,
        [
            (
                "Synthetic",
                [
                    [["학번", "성명"], ["2031123456", "가상학생"]],
                    [["전공", "교양", "총학점"], ["3", "2", "5"]],
                    [section("2031학년도 1학기"), KLAS_HEADERS, ["가상가", "전선", "3", "B0", ""]],
                ],
            )
        ],
    )
    result = parse_transcript(b"%PDF-synthetic mock")
    assert len(result.courses) == 1
    assert result.parse_warnings == []
    assert "2031123456" not in result.model_dump_json()
    assert "가상학생" not in result.model_dump_json()


def test_unknown_semester_section_clears_previous_context(monkeypatch):
    mock_pages(
        monkeypatch,
        [
            (
                "Synthetic",
                [
                    [
                        section("2031학년도 1학기"),
                        KLAS_HEADERS,
                        ["가상가", "전선", "3", "B0", ""],
                        section("2031학년도 3학기"),
                        KLAS_HEADERS,
                        ["가상제외", "전선", "3", "B0", ""],
                        section("2030학년도 2학기"),
                        KLAS_HEADERS,
                        ["가상나", "교선", "2", "P", ""],
                    ]
                ],
            )
        ],
    )
    result = parse_transcript(b"%PDF-synthetic mock")
    assert [course.name for course in result.courses] == ["가상가", "가상나"]
    assert [(course.year, course.term) for course in result.courses] == [(2031, "1"), (2030, "2")]
    assert result.parse_warnings


def test_outer_layout_container_is_not_parsed_again_as_course_rows(monkeypatch):
    from unittest.mock import MagicMock

    first = [section("2031학년도 1학기"), KLAS_HEADERS, ["가상가", "전선", "3", "B0", ""]]
    second = [section("2030학년도 2학기"), KLAS_HEADERS, ["가상나", "교선", "2", "P", ""]]
    document, _ = mock_pages(monkeypatch, [("Synthetic", [first + second, first, second])])
    outer = MagicMock()
    outer.bbox = (0, 0, 800, 800)
    outer.extract.return_value = first + second
    upper = MagicMock()
    upper.bbox = (20, 20, 760, 300)
    upper.extract.return_value = first
    lower = MagicMock()
    lower.bbox = (20, 350, 760, 700)
    lower.extract.return_value = second
    document.pages[0].find_tables.return_value = [outer, upper, lower]
    result = parse_transcript(b"%PDF-synthetic mock")
    assert [course.name for course in result.courses] == ["가상가", "가상나"]
    assert result.parse_warnings == []


def test_headerless_five_column_personal_metadata_is_not_a_course(monkeypatch):
    mock_pages(
        monkeypatch,
        [
            (
                "Synthetic first",
                [[section("2031학년도 1학기"), KLAS_HEADERS, ["가상가", "전선", "3", "B0", ""]]],
            ),
            ("Synthetic second", [[["가상학생", "가상학부", "3", "", ""]]]),
        ],
    )
    result = parse_transcript(b"%PDF-synthetic mock")
    assert [course.name for course in result.courses] == ["가상가"]
    assert result.parse_warnings
    assert "가상학생" not in result.model_dump_json()
    assert "가상학부" not in result.model_dump_json()


def test_malformed_course_header_before_valid_table_is_not_silently_omitted(monkeypatch):
    malformed_header = ["과목명", "이수구분", "학점", "성적", "미확인"]
    mock_pages(
        monkeypatch,
        [
            (
                "Synthetic",
                [
                    [
                        section("2031학년도 1학기"),
                        malformed_header,
                        ["가상제외", "전선", "3", "B0", ""],
                    ],
                    [section("2030학년도 2학기"), KLAS_HEADERS, ["가상정상", "교선", "2", "P", ""]],
                ],
            )
        ],
    )
    result = parse_transcript(b"%PDF-synthetic mock")
    assert [course.name for course in result.courses] == ["가상정상"]
    assert result.parse_warnings
    assert result.parse_warnings[0].row <= 3
