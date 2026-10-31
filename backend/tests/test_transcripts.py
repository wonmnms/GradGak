"""API contract tests using synthetic documents and bounded multipart uploads."""

import tempfile
from io import BytesIO
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from reportlab.pdfgen import canvas
from starlette import formparsers

from app.main import app
from app.routers import transcripts
from app.schemas.transcripts import Course, TranscriptParseResponse
from tests.test_transcript_parser import COURSE, HEADERS, make_pdf

client = TestClient(app)


def _pdf_with_text(text: str | None) -> bytes:
    stream = BytesIO()
    document = canvas.Canvas(stream)
    if text:
        document.drawString(40, 750, text)
    document.showPage()
    document.save()
    return stream.getvalue()


def _multipart(data: bytes, *, extra_header: bytes = b"") -> tuple[bytes, str]:
    boundary = "synthetic-boundary"
    body = (
        b"--synthetic-boundary\r\n"
        b'Content-Disposition: form-data; name="file"; filename="sample.pdf"\r\n'
        b"Content-Type: application/pdf\r\n"
        + extra_header
        + b"\r\n"
        + data
        + b"\r\n--synthetic-boundary--\r\n"
    )
    return body, f"multipart/form-data; boundary={boundary}"


@pytest.fixture
def parser_result(monkeypatch):
    result = TranscriptParseResponse(
        admission_year=2024,
        courses=[
            Course(
                year=2024,
                term="summer",
                course_code=None,
                name="합성 과목",
                category="전선",
                credits=1.5,
                grade="NP",
                is_retake=True,
            )
        ],
        parse_warnings=[{"row": 3, "message": "학점 값을 확인해 주세요."}],
    )
    parser = Mock(return_value=result)
    monkeypatch.setattr(transcripts, "parse_transcript", parser)
    return parser, result


def test_generated_table_pdf_parses_through_api():
    response = client.post(
        "/transcripts/parse",
        files={"file": ("synthetic.pdf", make_pdf([HEADERS, COURSE]), "application/pdf")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["admission_year"] is None
    assert data["courses"] == [
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
    ]
    assert data["parse_warnings"] == []


def test_upload_returns_contract_response(parser_result):
    parser, result = parser_result
    response = client.post(
        "/transcripts/parse",
        files={"file": ("sample.pdf", b"synthetic bytes", "application/octet-stream")},
    )
    assert response.status_code == 200
    assert response.json() == result.model_dump()
    parser.assert_called_once_with(b"synthetic bytes")


@pytest.mark.parametrize(
    "request_kwargs",
    [
        {},
        {"json": {"file": "sample.pdf"}},
        {"files": {"other": ("sample.pdf", b"x", "application/pdf")}},
        {"files": {"file": (None, "not a file")}},
        {
            "files": [
                ("file", ("first.pdf", b"x", "application/pdf")),
                ("file", ("second.pdf", b"y", "application/pdf")),
            ]
        },
    ],
)
def test_upload_requires_exactly_one_file_field(request_kwargs):
    response = client.post("/transcripts/parse", **request_kwargs)
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "file"]


def test_exact_file_limit_is_accepted(parser_result):
    parser, _ = parser_result
    pdf_bytes = b"x" * transcripts.MAX_FILE_BYTES
    response = client.post(
        "/transcripts/parse", files={"file": ("sample.pdf", pdf_bytes, "application/pdf")}
    )
    assert response.status_code == 200
    parser.assert_called_once_with(pdf_bytes)


def test_file_over_limit_is_rejected_before_parsing(parser_result):
    parser, _ = parser_result
    response = client.post(
        "/transcripts/parse",
        files={"file": ("sample.pdf", b"x" * (transcripts.MAX_FILE_BYTES + 1), "application/pdf")},
    )
    assert response.status_code == 413
    assert response.json()["detail"]["code"] == "FILE_TOO_LARGE"
    parser.assert_not_called()


@pytest.mark.parametrize("file_size", [1, transcripts.MAX_FILE_BYTES])
def test_multipart_overhead_limit_is_independent_of_file_size(parser_result, file_size):
    parser, _ = parser_result
    body, content_type = _multipart(
        b"x" * file_size, extra_header=b"X-Padding: " + b"x" * 65536 + b"\r\n"
    )
    response = client.post(
        "/transcripts/parse", content=body, headers={"Content-Type": content_type}
    )
    assert response.status_code == 413
    assert response.json()["detail"]["code"] == "FILE_TOO_LARGE"
    parser.assert_not_called()


def test_chunked_upload_without_content_length(parser_result):
    parser, _ = parser_result
    body, content_type = _multipart(b"chunked document")
    chunks = (body[offset : offset + 7] for offset in range(0, len(body), 7))
    response = client.post(
        "/transcripts/parse", content=chunks, headers={"Content-Type": content_type}
    )
    assert "content-length" not in response.request.headers
    assert response.status_code == 200
    parser.assert_called_once_with(b"chunked document")


def test_truncated_multipart_is_validation_error(parser_result):
    parser, _ = parser_result
    body, content_type = _multipart(b"document")
    body = body[: body.index(b"\r\n--synthetic-boundary--")]
    response = client.post(
        "/transcripts/parse", content=body, headers={"Content-Type": content_type}
    )
    assert response.status_code == 422
    parser.assert_not_called()


def test_large_upload_does_not_create_disk_temporary_files(monkeypatch, parser_result):
    def fail_disk_file(*args, **kwargs):
        pytest.fail("upload attempted to create a disk-spooled temporary file")

    monkeypatch.setattr(tempfile, "TemporaryFile", fail_disk_file)
    monkeypatch.setattr(tempfile, "SpooledTemporaryFile", fail_disk_file)
    monkeypatch.setattr(formparsers, "SpooledTemporaryFile", fail_disk_file)
    response = client.post(
        "/transcripts/parse",
        files={"file": ("sample.pdf", b"x" * (2 * 1024 * 1024), "application/pdf")},
    )
    assert response.status_code == 200


@pytest.mark.parametrize("pdf_bytes", [b"", b"not a PDF", b"%PDF-1.7\ncorrupt"])
def test_invalid_pdf_and_filename_are_not_reflected(pdf_bytes):
    private_filename = "private-student-2024123456.pdf"
    response = client.post(
        "/transcripts/parse", files={"file": (private_filename, pdf_bytes, "application/pdf")}
    )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "NOT_PDF"
    assert private_filename not in response.text
    assert "2024123456" not in response.text


@pytest.mark.parametrize(
    ("text", "code"),
    [(None, "NO_TEXT_LAYER"), ("Synthetic document without table", "TABLE_NOT_FOUND")],
)
def test_real_pdf_error_codes(text, code):
    response = client.post(
        "/transcripts/parse",
        files={"file": ("sample.pdf", _pdf_with_text(text), "application/pdf")},
    )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == code
    if code == "NO_TEXT_LAYER":
        assert response.json()["detail"]["message"]


def test_openapi_documents_file_upload_and_errors():
    operation = client.get("/openapi.json").json()["paths"]["/transcripts/parse"]["post"]
    request = operation["requestBody"]
    assert request["required"] is True
    schema = request["content"]["multipart/form-data"]["schema"]
    assert schema["required"] == ["file"]
    assert schema["properties"]["file"] == {"type": "string", "format": "binary"}
    assert {"200", "400", "413", "422"} <= operation["responses"].keys()


@pytest.mark.parametrize("credits", [float("nan"), float("inf"), float("-inf"), -1])
def test_course_rejects_nonfinite_or_negative_credits(credits):
    with pytest.raises(ValidationError):
        Course(
            year=2024,
            term="1",
            name="합성 과목",
            category="전선",
            credits=credits,
            grade=None,
            is_retake=False,
        )


def test_course_allows_nullable_code_and_future_grade():
    course = Course(
        year=2024,
        term="winter",
        name="합성 과목",
        category="전선",
        credits=0,
        grade=None,
        is_retake=False,
    )
    assert course.course_code is None
    assert course.grade is None
