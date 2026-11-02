"""Opt-in local checks; private PDF bytes and expected JSON never live in Git.

Set KLAS_TEXT_PDF, KLAS_IMAGE_PDF and KLAS_EXPECTED_JSON to local private paths.
Without all three, these integration tests are skipped. Failures disclose only
row indices/field names, never transcript values or extracted JSON.
"""

import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.transcript_parser import TranscriptParseError, parse_transcript

_FIELDS = ("year", "term", "course_code", "name", "category", "credits", "grade", "is_retake")


@pytest.fixture(scope="module")
def private_samples():
    values = {
        name: os.environ.get(name)
        for name in ("KLAS_TEXT_PDF", "KLAS_IMAGE_PDF", "KLAS_EXPECTED_JSON")
    }
    if not all(values.values()):
        pytest.skip("Private KLAS samples are opt-in via environment variables.")
    try:
        text_pdf = Path(values["KLAS_TEXT_PDF"]).read_bytes()
        image_pdf = Path(values["KLAS_IMAGE_PDF"]).read_bytes()
        expected = json.loads(Path(values["KLAS_EXPECTED_JSON"]).read_text(encoding="utf-8"))
        if isinstance(expected, dict):
            expected = expected["courses"]
    except Exception as error:
        pytest.fail(f"Private sample setup failed ({type(error).__name__}).", pytrace=False)
    if not isinstance(expected, list) or len(expected) != 45:
        pytest.fail(
            "Expected fixture must contain 45 independently verified courses.", pytrace=False
        )
    return text_pdf, image_pdf, expected


def _compare_private_courses(actual, expected):
    if len(actual) != 45:
        pytest.fail(f"Private PDF produced {len(actual)} courses; expected 45.", pytrace=False)
    for index, (received, reference) in enumerate(zip(actual, expected, strict=True), start=1):
        if set(received) != set(_FIELDS) or set(reference) != set(_FIELDS):
            pytest.fail(f"Private comparison field set mismatch at row {index}.", pytrace=False)
        for field in _FIELDS:
            if received[field] != reference[field]:
                pytest.fail(
                    f"Private comparison mismatch at row {index}, field {field}.", pytrace=False
                )


def test_private_converted_pdf_matches_all_45_expected_courses(private_samples):
    text_pdf, _, expected = private_samples
    try:
        result = parse_transcript(text_pdf)
    except Exception as error:
        pytest.fail(f"Private converted PDF failed ({type(error).__name__}).", pytrace=False)
    _compare_private_courses([course.model_dump() for course in result.courses], expected)
    if result.admission_year is not None:
        pytest.fail(
            "Private PDF without student-ID label must not infer an admission year.", pytrace=False
        )
    if result.parse_warnings:
        pytest.fail("Private converted PDF returned unexpected parsing warnings.", pytrace=False)


def test_private_converted_pdf_api_matches_all_45_expected_courses(private_samples):
    text_pdf, _, expected = private_samples
    try:
        response = TestClient(app).post(
            "/transcripts/parse", files={"file": ("private.pdf", text_pdf, "application/pdf")}
        )
        body = response.json()
    except Exception as error:
        pytest.fail(f"Private PDF API failed ({type(error).__name__}).", pytrace=False)
    if response.status_code != 200:
        pytest.fail(f"Private PDF API returned HTTP {response.status_code}.", pytrace=False)
    _compare_private_courses(body["courses"], expected)
    if body["admission_year"] is not None:
        pytest.fail(
            "Private PDF API must not infer an admission year without a student-ID label.",
            pytrace=False,
        )
    if body["parse_warnings"]:
        pytest.fail(
            "Private converted PDF API returned unexpected parsing warnings.", pytrace=False
        )


def test_private_printed_pdf_requires_text_layer_without_ocr(private_samples):
    _, image_pdf, _ = private_samples
    try:
        parse_transcript(image_pdf)
    except TranscriptParseError as error:
        if error.code != "NO_TEXT_LAYER":
            pytest.fail("Private image-only PDF returned the wrong error code.", pytrace=False)
    except Exception as error:
        pytest.fail(f"Private image-only PDF failed ({type(error).__name__}).", pytrace=False)
    else:
        pytest.fail("Private image-only PDF was accepted without a text layer.", pytrace=False)


def test_private_printed_pdf_api_returns_no_text_layer(private_samples):
    _, image_pdf, _ = private_samples
    try:
        response = TestClient(app).post(
            "/transcripts/parse", files={"file": ("private.pdf", image_pdf, "application/pdf")}
        )
        body = response.json()
    except Exception as error:
        pytest.fail(f"Private image-only PDF API failed ({type(error).__name__}).", pytrace=False)
    if response.status_code != 400 or body.get("detail", {}).get("code") != "NO_TEXT_LAYER":
        pytest.fail("Private image-only PDF API must return 400 NO_TEXT_LAYER.", pytrace=False)
