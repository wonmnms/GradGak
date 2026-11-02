"""Hypothetical footer layouts, not fixtures from a verified KLAS export."""

from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfgen.canvas import Canvas

from app.main import app
from app.services.transcript_parser import TranscriptParseError, parse_transcript
from tests.test_klas_transcript_parser import KLAS_HEADERS, _draw_table, section


def footer_pdf(*, unruled_course=False, ruled_course=False):
    """Draw a known course table followed by an invented final-page layout."""
    pdfmetrics.registerFont(UnicodeCIDFont("HYSMyeongJo-Medium"))
    stream = BytesIO()
    document = Canvas(stream, pagesize=(900, 1000))
    document.setFont("HYSMyeongJo-Medium", 10)
    _draw_table(
        document,
        [section("2031학년도 1학기"), KLAS_HEADERS, ["가상과목1", "전선", "3", "B0", ""]],
        top=920,
    )
    document.showPage()
    document.setFont("HYSMyeongJo-Medium", 10)
    document.drawString(30, 100, "합계: 3학점")
    document.drawString(30, 80, "출력일시: 2031-07-01 12:00:00")
    if unruled_course:
        document.drawString(30, 900, "2031학년도 1학기")
        document.drawString(30, 880, "과목명 이수구분 학점 성적 재수강여부")
        document.drawString(30, 860, "가상과목2 전선 3 B0")
    if ruled_course:
        _draw_table(
            document,
            [section("2031학년도 1학기"), KLAS_HEADERS, ["가상과목2", "전선", "3", "B0", ""]],
            top=920,
        )
    document.showPage()
    document.save()
    return stream.getvalue()


@pytest.mark.parametrize("unruled_course", [False, True], ids=["summary-only", "possible-course"])
def test_text_only_final_page_is_not_silently_discarded(unruled_course):
    # Summary keywords alone cannot prove that no course table failed extraction.
    with pytest.raises(TranscriptParseError) as error:
        parse_transcript(footer_pdf(unruled_course=unruled_course))
    assert error.value.code == "TABLE_NOT_FOUND"
    assert "가상과목" not in error.value.message
    assert "2031-07-01" not in error.value.message


@pytest.mark.parametrize("unruled_course", [False, True], ids=["summary-only", "possible-course"])
def test_text_only_final_page_returns_whole_document_error_through_api(unruled_course):
    response = TestClient(app).post(
        "/transcripts/parse",
        files={
            "file": ("synthetic.pdf", footer_pdf(unruled_course=unruled_course), "application/pdf")
        },
    )
    assert response.status_code == 400
    data = response.json()
    assert data["detail"]["code"] == "TABLE_NOT_FOUND"
    assert "courses" not in data
    assert "가상과목" not in response.text
    assert "2031-07-01" not in response.text


def test_footer_on_final_course_table_page_preserves_every_course():
    result = parse_transcript(footer_pdf(ruled_course=True))
    assert [course.name for course in result.courses] == ["가상과목1", "가상과목2"]
    assert result.parse_warnings == []
