"""API 명세의 이수과목과 PDF 파싱 응답. 개인정보 원문 필드는 두지 않는다."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

Year = Annotated[int, Field(ge=1900, le=2199)]
NonEmptyString = Annotated[str, Field(min_length=1)]


class Course(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    year: Year
    term: Literal["1", "2", "summer", "winter"]
    course_code: NonEmptyString | None = None
    name: NonEmptyString
    category: NonEmptyString
    credits: float = Field(ge=0, allow_inf_nan=False)
    grade: NonEmptyString | None = None
    is_retake: bool


class ParseWarning(BaseModel):
    row: int = Field(ge=1)
    message: str


class TranscriptParseResponse(BaseModel):
    admission_year: Year | None
    courses: list[Course]
    parse_warnings: list[ParseWarning]


class ParseErrorDetail(BaseModel):
    code: Literal["NOT_PDF", "NO_TEXT_LAYER", "TABLE_NOT_FOUND", "FILE_TOO_LARGE"]
    message: str


class ParseErrorResponse(BaseModel):
    detail: ParseErrorDetail
