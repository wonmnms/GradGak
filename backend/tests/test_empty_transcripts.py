"""Empty transcript policy using fictional, generated PDF documents."""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.transcript_parser import parse_transcript
from tests.test_klas_transcript_parser import KLAS_HEADERS, make_sectioned_pdf, section
from tests.test_transcript_parser import HEADERS, make_pdf


def empty_pdf(layout, with_blank_row=False):
    if layout == "explicit":
        rows = [HEADERS]
        if with_blank_row:
            rows.append([""] * len(HEADERS))
        return make_pdf(rows)
    rows = [section("2031학년도 1학기"), KLAS_HEADERS]
    if with_blank_row:
        rows.append([""] * len(KLAS_HEADERS))
    return make_sectioned_pdf([[rows]])


@pytest.mark.parametrize(("layout", "header_row"), [("explicit", 1), ("klas", 2)])
@pytest.mark.parametrize("with_blank_row", [False, True])
def test_recognized_empty_table_always_has_safe_warning(layout, header_row, with_blank_row):
    result = parse_transcript(empty_pdf(layout, with_blank_row))
    assert result.courses == []
    assert len(result.parse_warnings) == 1
    assert result.parse_warnings[0].row == header_row
    assert "과목 행이 없습니다" in result.parse_warnings[0].message


@pytest.mark.parametrize("layout", ["explicit", "klas"])
def test_all_invalid_rows_keep_their_specific_warning(layout):
    course = ["가상과목", "전선", "not-a-number", "B0", ""]
    if layout == "explicit":
        document = make_pdf([HEADERS, ["2031", "1", "TEST101", *course]])
        row_number = 2
    else:
        document = make_sectioned_pdf([[[section("2031학년도 1학기"), KLAS_HEADERS, course]]])
        row_number = 3
    result = parse_transcript(document)
    assert result.courses == []
    assert len(result.parse_warnings) == 1
    assert result.parse_warnings[0].row == row_number
    assert "학점" in result.parse_warnings[0].message
    assert "not-a-number" not in result.model_dump_json()


@pytest.mark.parametrize("layout", ["explicit", "klas"])
def test_api_keeps_empty_recognized_table_as_200_with_warning(layout):
    response = TestClient(app).post(
        "/transcripts/parse",
        files={"file": ("synthetic-empty.pdf", empty_pdf(layout), "application/pdf")},
    )
    assert response.status_code == 200
    assert response.json()["courses"] == []
    assert len(response.json()["parse_warnings"]) == 1
