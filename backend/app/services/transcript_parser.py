"""Read KLAS semester-section tables and explicit year/term tables in memory.

KLAS sections carry their year/term into the following course rows. Repeated
section headings on later pages continue the same semester without deduplication.
Only an established KLAS column layout may continue without a repeated header on
the next page. Blank grades become None; deletion annotations remain in the grade
string, and retake status comes solely from the explicit retake column.

Warnings use 1-based cumulative extracted-table row numbers (headers included).
Source rows, identities, and library exception details never enter diagnostics.
"""

import re
from io import BytesIO

import pdfplumber
from pdfminer.psexceptions import PSException
from pdfplumber.utils.exceptions import MalformedPDFException, PdfminerException
from pydantic import ValidationError

from app.schemas.transcripts import Course, ParseWarning, TranscriptParseResponse

_HEADER_ALIASES = {
    "연도": "year",
    "년도": "year",
    "수강연도": "year",
    "수강년도": "year",
    "학기": "term",
    "학수번호": "course_code",
    "과목코드": "course_code",
    "과목명": "name",
    "교과목명": "name",
    "이수구분": "category",
    "학점": "credits",
    "취득학점": "credits",
    "성적": "grade",
    "재수강": "is_retake",
    "재수강여부": "is_retake",
}
_COURSE_COLUMNS = {"name", "category", "credits", "grade", "is_retake"}
_REQUIRED_COLUMNS = _COURSE_COLUMNS | {"year", "term"}
_TERMS = {
    "1": "1",
    "1학기": "1",
    "2": "2",
    "2학기": "2",
    "summer": "summer",
    "하계": "summer",
    "여름": "summer",
    "하계계절학기": "summer",
    "여름계절학기": "summer",
    "winter": "winter",
    "동계": "winter",
    "겨울": "winter",
    "동계계절학기": "winter",
    "겨울계절학기": "winter",
}
_RETAKE_TRUE = {"y", "yes", "true", "1", "o", "○", "재수강"}
_RETAKE_FALSE = {"", "n", "no", "false", "0", "x", "×"}
_STUDENT_ID = re.compile(r"(?<![가-힣A-Za-z])학\s*번\s*[:：]?\s*([0-9]{8,14})(?![0-9])")
_SEMESTER_SECTION = re.compile(r"([0-9]{4})학년도(?:(1|2)학기|계절학기\((하계|동계)\))")
_CREDITS = re.compile(r"[0-9]+(?:\.[0-9]+)?")
# Headerless continuation is intentionally narrower than an explicitly headed table.
_CONTINUATION_CATEGORIES = {
    "전필",
    "전선",
    "교필",
    "교선",
    "전공필수",
    "전공선택",
    "교양필수",
    "교양선택",
}


class TranscriptParseError(Exception):
    """Expected failures with authored, user-facing messages."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class _UnrecognizedRow(Exception):
    """Only contains safe messages, never extracted source data."""


def _cell(value: str | None) -> str:
    return re.sub(r"[\r\n]+", " ", value or "").strip()


def _header_indices(
    row: list[str | None], required: set[str] = _REQUIRED_COLUMNS
) -> dict[str, int] | None:
    indices = {}
    for index, value in enumerate(row):
        alias = _HEADER_ALIASES.get("".join(_cell(value).split()))
        if alias is not None:
            if alias in indices:
                return None
            indices[alias] = index
    return indices if required <= indices.keys() else None


def _section(row: list[str | None]) -> tuple[bool, tuple[int, str] | None]:
    """Return whether a row is a section, and its validated semester if known."""
    cells = [_cell(value) for value in row]
    nonblank = [value for value in cells if value]
    if len(nonblank) != 1:
        return False, None
    text = "".join(nonblank[0].split())
    if "학년도" not in text:
        return False, None
    match = _SEMESTER_SECTION.fullmatch(text)
    if match is None or not 1900 <= int(match[1]) <= 2199:
        return True, None
    term = match[2] or {"하계": "summer", "동계": "winter"}[match[3]]
    return True, (int(match[1]), term)


def _admission_year(text: str) -> int | None:
    years = {
        int(match[:4]) for match in _STUDENT_ID.findall(text) if 1900 <= int(match[:4]) <= 2199
    }
    return years.pop() if len(years) == 1 else None


def _parse_course(
    row: list[str | None], indices: dict[str, int], semester: tuple[int, str] | None = None
) -> Course:
    values = {key: _cell(row[index]) for key, index in indices.items()}
    if semester is not None:
        values["year"], values["term"] = str(semester[0]), semester[1]
    if not re.fullmatch(r"[0-9]{4}", values.get("year", "")):
        raise _UnrecognizedRow("수강 연도를 인식하지 못해 이 행을 제외했습니다.")
    term = _TERMS.get("".join(values.get("term", "").split()).lower())
    if term is None:
        raise _UnrecognizedRow("수강 학기를 인식하지 못해 이 행을 제외했습니다.")
    if not _CREDITS.fullmatch(values["credits"]):
        raise _UnrecognizedRow("학점을 숫자로 인식하지 못해 이 행을 제외했습니다.")
    if not values["name"] or not values["category"]:
        raise _UnrecognizedRow("과목명 또는 이수구분이 비어 있어 이 행을 제외했습니다.")
    retake = values["is_retake"].lower()
    if retake not in _RETAKE_TRUE | _RETAKE_FALSE:
        raise _UnrecognizedRow("재수강 표시를 인식하지 못해 이 행을 제외했습니다.")
    try:
        return Course(
            year=int(values["year"]),
            term=term,
            course_code=values.get("course_code") or None,
            name=values["name"],
            category=values["category"],
            credits=float(values["credits"]),
            grade=values["grade"] or None,
            is_retake=retake in _RETAKE_TRUE,
        )
    except ValidationError:
        raise _UnrecognizedRow("과목 필드의 값이 유효하지 않아 이 행을 제외했습니다.") from None


def _no_text_layer_error() -> TranscriptParseError:
    return TranscriptParseError(
        "NO_TEXT_LAYER",
        "PDF의 전체 또는 일부 페이지에서 텍스트를 읽을 수 없습니다. KLAS에서 내려받은 "
        "텍스트 선택이 가능한 원본 PDF를 사용해 주세요. "
        "Microsoft Print to PDF로 다시 인쇄한 파일은 피해주세요.",
    )


def _is_klas_document(pages: list[list[list[list[str | None]]]]) -> bool:
    """Require both a semester section and the corresponding course headers."""
    for tables in pages:
        for table in tables:
            section_seen = False
            for row in table:
                is_section, semester = _section(row)
                if is_section:
                    section_seen = semester is not None
                elif section_seen and _header_indices(row, _COURSE_COLUMNS) is not None:
                    return True
    return False


def _warn(row: int, message: str) -> ParseWarning:
    return ParseWarning(row=row, message=message)


def _read_tables(
    pages: list[list[list[list[str | None]]]],
) -> tuple[list[Course], list[ParseWarning]]:
    courses, warnings = [], []
    klas_mode = _is_klas_document(pages)
    table_found = False
    first_header_row = 0
    row_number = 0
    semester = None
    carry_indices = None
    carry_width = 0
    for tables in pages:
        first_nonempty_table = True
        for table in tables:
            first_row = next((i for i, row in enumerate(table) if any(_cell(v) for v in row)), None)
            if first_row is None:
                row_number += len(table)
                continue
            indices = None
            width = 0
            mode = None
            recognized = False
            first_warning_row = row_number + first_row + 1
            # A headerless continuation is restricted to the first nonempty table
            # on the next page, and only after a KLAS header established its layout.
            if (
                klas_mode
                and first_nonempty_table
                and carry_indices is not None
                and semester is not None
                and all(
                    len(row) == carry_width
                    and (
                        not any(_cell(value) for value in row)
                        or _cell(row[carry_indices["category"]]) in _CONTINUATION_CATEGORIES
                    )
                    for row in table
                )
            ):
                indices, width, mode = carry_indices, carry_width, "klas"
            first_nonempty_table = False
            for row in table:
                row_number += 1
                if not any(_cell(value) for value in row):
                    continue
                is_section, section_semester = _section(row)
                if klas_mode and is_section:
                    semester = section_semester
                    indices, mode, carry_indices = None, None, None
                    if semester is None:
                        warnings.append(
                            _warn(
                                row_number,
                                "학기 구획을 인식하지 못했습니다. "
                                "다음 학기 구획까지의 과목을 확인해 주세요.",
                            )
                        )
                    continue
                header = _header_indices(row)
                if header is not None:
                    indices, width, mode = header, len(row), "explicit"
                    table_found = recognized = True
                    first_header_row = first_header_row or row_number
                    carry_indices = None
                    continue
                section_header = _header_indices(row, _COURSE_COLUMNS)
                if klas_mode and section_header is not None:
                    if semester is None:
                        warnings.append(
                            _warn(
                                row_number,
                                "과목 머리글에 대응하는 학기 구획을 확인하지 못했습니다.",
                            )
                        )
                        indices, mode, carry_indices = None, None, None
                    else:
                        indices, width, mode = section_header, len(row), "klas"
                        carry_indices, carry_width = indices, width
                        table_found = recognized = True
                        first_header_row = first_header_row or row_number
                    continue
                if indices is None:
                    continue
                recognized = True
                if len(row) != width:
                    warnings.append(
                        _warn(row_number, "열 개수가 머리글과 달라 이 행을 제외했습니다.")
                    )
                    continue
                try:
                    courses.append(
                        _parse_course(row, indices, semester if mode == "klas" else None)
                    )
                except _UnrecognizedRow as error:
                    warnings.append(_warn(row_number, str(error)))
            suspicious_table = any(
                _section(row)[0]
                or {"name", "credits"}
                <= {_HEADER_ALIASES.get("".join(_cell(value).split())) for value in row}
                for row in table
            )
            if not recognized and (not klas_mode or table_found or suspicious_table):
                warnings.append(
                    _warn(
                        first_warning_row,
                        "인식하지 못한 표가 있어 일부 이수내역이 "
                        "누락되었을 수 있습니다. PDF 원본과 대조하여 확인해 주세요.",
                    )
                )
                carry_indices = None
                if klas_mode:
                    semester = None
    if not table_found:
        raise TranscriptParseError(
            "TABLE_NOT_FOUND", "이수내역 표를 찾지 못했습니다. KLAS 이수내역 PDF인지 확인해 주세요."
        )
    # A recognized table is a valid response even when empty. Never silently
    # return an empty result: invalid rows already explain themselves; a table
    # containing only headers/blank rows needs its own safe warning.
    if not courses and not warnings:
        warnings.append(
            _warn(
                first_header_row,
                "과목 표의 머리글은 확인했지만 읽을 수 있는 과목 행이 없습니다. "
                "PDF 원본을 확인하거나 검수 화면에서 과목을 추가해 주세요.",
            )
        )
    warnings.sort(key=lambda warning: warning.row)
    return courses, warnings


def _extract_tables(page) -> list[list[list[str | None]]]:
    """Keep actual grids, excluding layout containers enclosing other tables.

    KLAS print exports can expose an outer frame whose single cell repeats all
    text in an inner course grid. Geometric containment avoids parsing that text
    twice or treating the wrapper as a malformed semester section.
    """
    tables = list(page.find_tables())
    if not tables:
        return page.extract_tables()

    def contains(outer, inner) -> bool:
        left, top, right, bottom = outer.bbox
        x0, y0, x1, y1 = inner.bbox
        return (
            (left, top, right, bottom) != (x0, y0, x1, y1)
            and left <= x0 + 0.01
            and top <= y0 + 0.01
            and right >= x1 - 0.01
            and bottom >= y1 - 0.01
        )

    return [
        table.extract()
        for table in tables
        if not any(contains(table, inner) for inner in tables if inner is not table)
    ]


def parse_transcript(pdf_bytes: bytes) -> TranscriptParseResponse:
    """Extract course rows without saving uploads or applying graduation rules."""
    if not pdf_bytes.startswith(b"%PDF-"):
        raise TranscriptParseError("NOT_PDF", "PDF 파일을 업로드해 주세요.")
    text_parts, pages = [], []
    try:
        with BytesIO(pdf_bytes) as stream, pdfplumber.open(stream) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                if not page_text.strip() and page.images:
                    raise _no_text_layer_error()
                text_parts.append(page_text)
                page_tables = _extract_tables(page)
                if page_text.strip() and not page_tables:
                    raise TranscriptParseError(
                        "TABLE_NOT_FOUND",
                        "텍스트는 있지만 표를 인식하지 못한 페이지가 있습니다. "
                        "일부 이수내역의 누락을 막기 위해 처리를 중단했습니다.",
                    )
                pages.append(page_tables)
    except (PSException, PdfminerException, MalformedPDFException, ValueError, EOFError, OSError):
        raise TranscriptParseError(
            "NOT_PDF", "PDF를 열 수 없습니다. 정상적으로 열리고 암호가 없는 PDF를 업로드해 주세요."
        ) from None
    text = "\n".join(text_parts)
    if not text.strip():
        raise _no_text_layer_error()
    courses, warnings = _read_tables(pages)
    return TranscriptParseResponse(
        admission_year=_admission_year(text), courses=courses, parse_warnings=warnings
    )
