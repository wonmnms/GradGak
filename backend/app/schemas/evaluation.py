"""졸업요건 판정 엔진의 입력·출력 스키마.

입력 `EvaluationCourse`는 과목 매칭이 끝난 과목의 최소 형태다. 매칭 결과를 이 형태로
바꾸는 일은 `/evaluate` 라우터(#18)가 한다. 출력은 docs/api-spec.md의 `POST /evaluate`
응답 200 형식을 따르되, 아직 명세에 없는 값·필드는 아래 주석에 표시했다.
"""

from typing import Literal

from pydantic import BaseModel, Field

STATUS_MET = "met"
STATUS_UNMET = "unmet"
# api-spec의 status 값은 met/unmet 뿐이다. 데이터가 없어 판정할 수 없는 상태를 나타내는
# 값은 명세에 아직 없으므로 임시 상수로만 둔다(api-spec 변경 필요).
STATUS_PENDING = "pending"

Status = Literal["met", "unmet", "pending"]


class EvaluationCourse(BaseModel):
    """매칭이 끝난 이수과목 1개."""

    index: int = Field(ge=0, description="요청 courses 배열의 위치(0부터)")
    course_id: int | None = Field(description="매칭된 courses.course_id. 매칭 실패면 None")
    name: str = Field(description="과목명 (PDF 표기 그대로)")
    course_code: str | None = None
    credits: float = Field(ge=0, description="요청(PDF)의 학점")
    grade: str | None = Field(description="성적 (PDF 표기 그대로). None은 수강 예정")
    category: str | None = Field(default=None, description="이수구분 (PDF 표기 그대로)")
    is_retake: bool = False


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
    # api-spec에 없는 필드: 판정 보류 사유 (api-spec 변경 필요)
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
    # 이하 api-spec에 없는 필드 (api-spec 변경 필요)
    excluded_courses: list[CourseNotice] = Field(
        default_factory=list, description="성적·재수강 정책으로 학점·이수에서 제외한 과목"
    )
    pending_data: list[str] = Field(
        default_factory=list, description="규칙 데이터가 미완성이라 판정을 보류한 항목"
    )
    warnings: list[str] = Field(default_factory=list)
