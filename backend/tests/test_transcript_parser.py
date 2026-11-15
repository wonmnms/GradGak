"""Synthetic PDF and extracted-row tests; no real KLAS fixture is included."""

from io import BytesIO
from unittest.mock import MagicMock

import pytest
from pdfminer.pdfexceptions import PDFTypeError
from pdfminer.psexceptions import PSSyntaxError
from pdfplumber.utils.exceptions import MalformedPDFException, PdfminerException
from PIL import Image
from reportlab.lib import colors
from reportlab.lib.pdfencrypt import StandardEncryption
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import Table, TableStyle

from app.services import transcript_parser
from app.services.transcript_parser import TranscriptParseError, parse_transcript

HEADERS = ["연도", "학기", "학수번호", "과목명", "이수구분", "학점", "성적", "재수강"]
COURSE = ["2024", "1학기", "TEST101", "합성 과목", "전필", "3", "A0", ""]


def make_pdf(rows=None, *, text="Synthetic transcript", encrypted=False, image_only=False):
    """Build a fictional table in memory, without personal data or disk files."""
    stream = BytesIO()
    encryption = StandardEncryption("test-password") if encrypted else None
    canvas = Canvas(stream, pagesize=(900, 800), encrypt=encryption)
    pdfmetrics.registerFont(UnicodeCIDFont("HYSMyeongJo-Medium"))
    canvas.setFont("HYSMyeongJo-Medium", 10)
    if text:
        canvas.drawString(20, 760, text)
    if image_only:
        canvas.drawImage(ImageReader(Image.new("RGB", (10, 10), "white")), 20, 20, 100, 100)
    if rows:
        table = Table(rows, colWidths=[80] * len(rows[0]), rowHeights=[28] * len(rows))
        table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, -1), "HYSMyeongJo-Medium"),
                    ("GRID", (0, 0), (-1, -1), 1, colors.black),
                ]
            )
        )
        table.wrapOn(canvas, 850, 700)
        table.drawOn(canvas, 20, 650 - 28 * len(rows))
    canvas.showPage()
    canvas.save()
    return stream.getvalue()


def mock_pages(monkeypatch, pages):
    """Use controlled extraction for layouts not claimed as actual KLAS output."""
    document = MagicMock()
    document.__enter__.return_value = document
    document.pages = []
    for text, tables in pages:
        page = MagicMock()
        page.images = []
        page.extract_text.return_value = text
        page.extract_tables.return_value = tables
        document.pages.append(page)
    opener = MagicMock(return_value=document)
    monkeypatch.setattr(transcript_parser.pdfplumber, "open", opener)
    return document, opener


def parse_rows(monkeypatch, rows, *, text="Synthetic transcript"):
    mock_pages(monkeypatch, [(text, [rows])])
    return parse_transcript(b"%PDF-synthetic mock")


def test_generated_pdf_exercises_real_text_and_table_extraction():
    result = parse_transcript(make_pdf([HEADERS, COURSE], text="학번: 2024123456"))
    assert result.model_dump() == {
        "admission_year": 2024,
        "courses": [
            {
                "year": 2024,
                "term": "1",
                "course_code": "TEST101",
                "name": "합성 과목",
                "category": "전필",
                "credits": 3.0,
                "grade": "A0",
                "is_retake": False,
            }
        ],
        "parse_warnings": [],
    }
    assert "2024123456" not in result.model_dump_json()


def test_generated_pdf_with_reordered_columns_and_without_course_code():
    rows = [
        ["교과목명", "수강년도", "학기", "취득학점", "이수구분", "재수강여부", "성적"],
        ["합성 실습", "2025", "여름", "1.5", "전선", "Y", "P"],
    ]
    result = parse_transcript(make_pdf(rows))
    course = result.courses[0]
    assert (course.name, course.year, course.term, course.credits) == (
        "합성 실습",
        2025,
        "summer",
        1.5,
    )
    assert course.course_code is None
    assert course.is_retake is True
    assert result.admission_year is None


@pytest.mark.parametrize("payload", [b"", b"not a PDF", b"%PDF-damaged"])
def test_non_pdf_or_damaged_pdf_has_safe_error(payload):
    with pytest.raises(TranscriptParseError) as error:
        parse_transcript(payload)
    assert error.value.code == "NOT_PDF"
    assert str(payload) not in error.value.message


def test_generated_encrypted_pdf_is_rejected():
    with pytest.raises(TranscriptParseError) as error:
        parse_transcript(make_pdf([HEADERS, COURSE], encrypted=True))
    assert error.value.code == "NOT_PDF"
    assert "test-password" not in error.value.message


def test_generated_pdf_without_text_has_save_instructions():
    with pytest.raises(TranscriptParseError) as error:
        parse_transcript(make_pdf(text=""))
    assert error.value.code == "NO_TEXT_LAYER"
    assert "Microsoft Print to PDF" in error.value.message


def test_generated_text_pdf_without_transcript_table_is_rejected():
    with pytest.raises(TranscriptParseError) as error:
        parse_transcript(make_pdf(text="Some other document"))
    assert error.value.code == "TABLE_NOT_FOUND"


@pytest.mark.parametrize(
    ("term", "expected"),
    [("1", "1"), ("2학기", "2"), ("하계", "summer"), ("겨울 계절학기", "winter")],
)
def test_explicit_semester_values_are_converted(monkeypatch, term, expected):
    row = COURSE.copy()
    row[1] = term
    assert parse_rows(monkeypatch, [HEADERS, row]).courses[0].term == expected


@pytest.mark.parametrize(
    ("column", "value"),
    [
        (0, "1학년"),
        (0, "1899"),
        (0, "2200"),
        (1, "3학기"),
        (1, "2024-1"),
        (3, ""),
        (4, None),
        (5, "NaN"),
        (5, "inf"),
        (5, "-3"),
        (5, "3학점"),
        (7, "알 수 없음"),
    ],
)
def test_invalid_rows_warn_and_leave_valid_courses(monkeypatch, column, value):
    invalid = COURSE.copy()
    invalid[column] = value
    result = parse_rows(monkeypatch, [HEADERS, invalid, COURSE])
    assert len(result.courses) == 1
    assert [warning.row for warning in result.parse_warnings] == [2]


def test_warnings_do_not_echo_extracted_private_text(monkeypatch):
    row = COURSE.copy()
    row[5] = "홍길동 2024123456"
    result = parse_rows(monkeypatch, [HEADERS, row])
    assert result.courses == []
    assert len(result.parse_warnings) == 1
    assert "홍길동" not in result.model_dump_json()
    assert "2024123456" not in result.model_dump_json()


@pytest.mark.parametrize("missing_index", [0, 1, 3, 4, 5, 6, 7])
def test_missing_required_header_is_not_guessed(monkeypatch, missing_index):
    headers = HEADERS.copy()
    headers[missing_index] = "미확인 열"
    with pytest.raises(TranscriptParseError) as error:
        parse_rows(monkeypatch, [headers, COURSE])
    assert error.value.code == "TABLE_NOT_FOUND"


def test_duplicate_headers_are_ambiguous(monkeypatch):
    with pytest.raises(TranscriptParseError) as error:
        parse_rows(monkeypatch, [HEADERS + ["학점"], COURSE + ["3"]])
    assert error.value.code == "TABLE_NOT_FOUND"


def test_missing_year_in_merged_cell_is_not_inherited(monkeypatch):
    second = COURSE.copy()
    second[0] = None
    result = parse_rows(monkeypatch, [HEADERS, COURSE, second])
    assert len(result.courses) == 1
    assert [warning.row for warning in result.parse_warnings] == [3]


def test_repeated_headers_blank_rows_and_continuous_warning_numbers(monkeypatch):
    bad = COURSE.copy()
    bad[5] = "bad"
    mock_pages(
        monkeypatch,
        [
            ("Synthetic page 1", [[["Other table"]], [HEADERS, COURSE, HEADERS]]),
            ("Synthetic page 2", [[HEADERS, [None] * 8, bad, COURSE]]),
        ],
    )
    result = parse_transcript(b"%PDF-synthetic mock")
    assert len(result.courses) == 2
    assert [warning.row for warning in result.parse_warnings] == [1, 7]


def test_row_width_mismatch_warns_instead_of_shifting_columns(monkeypatch):
    result = parse_rows(monkeypatch, [HEADERS, COURSE[:-1], COURSE])
    assert len(result.courses) == 1
    assert [warning.row for warning in result.parse_warnings] == [2]


def test_failed_grades_and_retake_attempts_are_not_filtered_or_deduplicated(monkeypatch):
    rows = [HEADERS]
    for grade, retake in [("F", ""), ("NP", ""), ("A+", "재수강")]:
        row = COURSE.copy()
        row[6], row[7] = grade, retake
        rows.append(row)
    result = parse_rows(monkeypatch, rows)
    assert [course.grade for course in result.courses] == ["F", "NP", "A+"]
    assert [course.is_retake for course in result.courses] == [False, False, True]


@pytest.mark.parametrize(
    ("text", "year"),
    [
        ("학번: 2024123456", 2024),
        ("학 번：2025123456", 2025),
        ("2024123456", None),
        ("수강 연도: 2024", None),
        ("학번: 2024", None),
        ("학번: 2024123456\n학번: 2025123456", None),
    ],
)
def test_admission_year_requires_labelled_unambiguous_student_id(monkeypatch, text, year):
    result = parse_rows(monkeypatch, [HEADERS, COURSE], text=text)
    assert result.admission_year == year


def test_pdf_document_and_stream_are_closed_on_success(monkeypatch):
    document, opener = mock_pages(monkeypatch, [("Synthetic", [[HEADERS, COURSE]])])
    parse_transcript(b"%PDF-synthetic mock")
    document.__exit__.assert_called_once()
    assert opener.call_args.args[0].closed


def test_pdf_document_and_stream_are_closed_when_extraction_fails(monkeypatch):
    document, opener = mock_pages(monkeypatch, [("Synthetic", [])])
    document.pages[0].extract_tables.side_effect = ValueError("홍길동 2024123456")
    with pytest.raises(TranscriptParseError) as error:
        parse_transcript(b"%PDF-synthetic mock")
    document.__exit__.assert_called_once()
    assert opener.call_args.args[0].closed
    assert error.value.code == "NOT_PDF"
    assert "홍길동" not in error.value.message


def test_mixed_document_with_image_only_page_is_not_silently_partial(monkeypatch):
    document, _ = mock_pages(monkeypatch, [("Synthetic", [[HEADERS, COURSE]]), ("", [])])
    document.pages[1].images = [{"synthetic": "image"}]
    with pytest.raises(TranscriptParseError) as error:
        parse_transcript(b"%PDF-synthetic mock")
    assert error.value.code == "NO_TEXT_LAYER"


def test_blank_page_does_not_hide_valid_courses(monkeypatch):
    mock_pages(monkeypatch, [("Synthetic", [[HEADERS, COURSE]]), ("", [])])
    result = parse_transcript(b"%PDF-synthetic mock")
    assert len(result.courses) == 1


def test_name_line_breaks_are_spaces_and_inner_spacing_is_preserved(monkeypatch):
    row = COURSE.copy()
    row[3] = "  합성  과목\n실습  "
    result = parse_rows(monkeypatch, [HEADERS, row])
    assert result.courses[0].name == "합성  과목 실습"


def test_headerless_continuation_table_warns_instead_of_silent_omission(monkeypatch):
    mock_pages(
        monkeypatch,
        [("Synthetic page 1", [[HEADERS, COURSE]]), ("Synthetic page 2", [[COURSE, COURSE]])],
    )
    result = parse_transcript(b"%PDF-synthetic mock")
    assert len(result.courses) == 1
    assert [warning.row for warning in result.parse_warnings] == [3]
    assert "누락" in result.parse_warnings[0].message


def test_unrecognized_table_before_transcript_also_warns_safely(monkeypatch):
    mock_pages(monkeypatch, [("Synthetic", [[["홍길동", "2024123456"]], [HEADERS, COURSE]])])
    result = parse_transcript(b"%PDF-synthetic mock")
    assert [warning.row for warning in result.parse_warnings] == [1]
    assert "홍길동" not in result.model_dump_json()
    assert "2024123456" not in result.model_dump_json()


@pytest.mark.parametrize(
    "exception", [PDFTypeError, PSSyntaxError, PdfminerException, MalformedPDFException]
)
def test_pdfminer_errors_map_to_safe_not_pdf(monkeypatch, exception):
    document, _ = mock_pages(monkeypatch, [("Synthetic", [])])
    document.pages[0].extract_tables.side_effect = exception("홍길동 2024123456")
    with pytest.raises(TranscriptParseError) as error:
        parse_transcript(b"%PDF-synthetic mock")
    assert error.value.code == "NOT_PDF"
    assert "홍길동" not in error.value.message
    assert "2024123456" not in error.value.message


def test_generated_image_only_pdf_requires_selectable_original():
    with pytest.raises(TranscriptParseError) as error:
        parse_transcript(make_pdf(text="", image_only=True))
    assert error.value.code == "NO_TEXT_LAYER"


def test_text_page_without_extractable_table_does_not_silently_drop_courses(monkeypatch):
    mock_pages(
        monkeypatch,
        [("Synthetic page 1", [[HEADERS, COURSE]]), ("Unrecognized continuation", [])],
    )
    with pytest.raises(TranscriptParseError) as error:
        parse_transcript(b"%PDF-synthetic mock")
    assert error.value.code == "TABLE_NOT_FOUND"
