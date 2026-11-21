"""졸업요건 판정 엔진의 입력·출력 스키마.

입력 `EvaluationCourse`는 과목 매칭이 끝난 과목의 최소 형태다. 매칭 결과를 이 형태로
바꾸는 일은 `app/services/evaluation_input.py`가 한다.
출력은 docs/api-spec.md의 `POST /evaluate` 응답 200 형식을 따른다.
"""

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.transcripts import Course, Year

STATUS_MET = "met"
STATUS_UNMET = "unmet"
# 데이터가 없어 판정할 수 없는 상태(api-spec에 정의됨).
STATUS_PENDING = "pending"

Status = Literal["met", "unmet", "pending"]


class EvaluateRequest(BaseModel):
    """`POST /evaluate` 요청 (docs/api-spec.md)."""

    admission_year: Year
    program: Literal["engineering", "general"]
    sub_major: Literal["software", "ai"]
    thesis_passed: bool
    topcit_taken: bool
    courses: list[Course]


class EvaluateErrorDetail(BaseModel):
    code: Literal["UNSUPPORTED_ADMISSION_YEAR", "UNSUPPORTED_SCOPE", "INVALID_RULE_DATA"]
    message: str


class EvaluateErrorResponse(BaseModel):
    detail: EvaluateErrorDetail


class EvaluationCourse(BaseModel):
    """매칭이 끝난 이수과목 1개."""

    index: int = Field(ge=0, description="요청 courses 배열의 위치(0부터)")
    course_id: int | None = Field(description="매칭된 courses.course_id. 매칭 실패면 None")
    name: str = Field(description="과목명 (PDF 표기 그대로)")
    course_code: str | None = None
    credits: float = Field(ge=0, allow_inf_nan=False, description="요청(PDF)의 학점")
    grade: str | None = Field(description="성적 (PDF 표기 그대로). None은 수강 예정")
    category: str | None = Field(default=None, description="이수구분 (PDF 표기 그대로)")
    is_retake: bool = False
    ambiguous: bool = Field(
        default=False, description="course_id=None인 이유가 매칭 실패가 아니라 후보 여러 개(모호)"
    )
    equivalent_course_ids: list[int] = Field(
        default_factory=list,
        description="verified 대체·인정 대상 course_id(단방향, 연쇄 없음). 학점은 세지 않는다",
    )


class GroupCourseResult(BaseModel):
    course_code: str | None
    name: str
    completed: bool


class CourseGroupResult(BaseModel):
    id: str
    label: str
    status: Status
    required_count: int
    completed_count: int
    courses: list[GroupCourseResult]


class NonCreditResult(BaseModel):
    id: str
    label: str
    status: Status


class CreditResult(BaseModel):
    required: int | None
    earned: float | None
    remaining: float | None
    status: Status


class CategoryResult(BaseModel):
    id: str
    label: str
    required: int | None
    earned: float | None
    remaining: float | None
    status: Status
    # 판정 보류 사유 (api-spec 참고)
    reason: str | None = None


class MissingCourse(BaseModel):
    course_code: str | None
    name: str
    credits: int | None
    category: str | None = None


class ProgramResult(BaseModel):
    program: Literal["engineering", "general"]
    status: Status
    total: CreditResult
    categories: list[CategoryResult]
    course_groups: list[CourseGroupResult]
    missing_required_courses: list[MissingCourse]


class CourseNotice(BaseModel):
    index: int
    name: str
    reason: str


class EvaluationResult(BaseModel):
    graduation_status: Status
    common_requirements: list[CourseGroupResult | NonCreditResult]
    program_results: list[ProgramResult]
    unmatched_courses: list[CourseNotice]
    excluded_courses: list[CourseNotice] = Field(
        default_factory=list, description="성적·재수강 정책으로 학점·이수에서 제외한 과목"
    )
    pending_data: list[str] = Field(
        default_factory=list, description="규칙 데이터가 미완성이라 판정을 보류한 항목"
    )
    warnings: list[str] = Field(default_factory=list)
