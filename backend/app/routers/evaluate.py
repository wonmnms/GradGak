"""졸업요건 판정 API. 규칙·매칭·판정 서비스를 연결만 한다(정책은 각 서비스에 있다)."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.evaluation import EvaluateErrorResponse, EvaluateRequest, EvaluationResult
from app.services.course_matching import CatalogValidationError, match_courses
from app.services.evaluation import evaluate
from app.services.evaluation_input import build_scope_inputs, evaluation_scopes
from app.services.rule_errors import InvalidRuleDataError
from app.services.rule_repository import RuleScopeNotFound, get_rule_bundle, has_admission_year
from app.services.sql_course_catalog import SqlCourseCatalogRepository

router = APIRouter(tags=["evaluate"])


def _unsupported(session: Session, admission_year: int) -> HTTPException:
    # 내부 예외 메시지(범위·ID)는 응답에 넣지 않는다.
    if not has_admission_year(session, admission_year):
        detail = {
            "code": "UNSUPPORTED_ADMISSION_YEAR",
            "message": f"{admission_year}학번 졸업요건은 아직 지원하지 않습니다.",
        }
    else:
        detail = {
            "code": "UNSUPPORTED_SCOPE",
            "message": "선택한 프로그램·세부전공의 졸업요건 데이터가 없습니다.",
        }
    return HTTPException(status_code=400, detail=detail)


def _invalid_rule_data() -> HTTPException:
    # 카탈로그·규칙 데이터 결함. 내부 예외 메시지는 응답에 넣지 않는다.
    detail = {
        "code": "INVALID_RULE_DATA",
        "message": "졸업요건 데이터에 문제가 있어 판정할 수 없습니다. 관리자에게 문의해 주세요.",
    }
    return HTTPException(status_code=500, detail=detail)


@router.post(
    "/evaluate",
    response_model=EvaluationResult,
    responses={
        400: {"model": EvaluateErrorResponse, "description": "지원하지 않는 입학년도·범위"},
        500: {"model": EvaluateErrorResponse, "description": "졸업요건 데이터 결함"},
    },
)
def evaluate_graduation(
    request: EvaluateRequest, session: Annotated[Session, Depends(get_db)]
) -> EvaluationResult:
    """DB 규칙 데이터로만 졸업요건을 판정한다. 요청 데이터는 저장하지 않는다."""
    try:
        rule_bundle = get_rule_bundle(
            session, request.admission_year, request.program, request.sub_major
        )
        scope_results = {
            program: match_courses(
                request.courses,
                SqlCourseCatalogRepository(
                    session, program=program, sub_major=request.sub_major
                ).load_snapshot(request.admission_year),
            )
            for program in evaluation_scopes(request.program)
        }
        completed, duplicates = build_scope_inputs(request.courses, scope_results)
        result = evaluate(rule_bundle, completed, request.thesis_passed, request.topcit_taken)
    except RuleScopeNotFound as exc:
        raise _unsupported(session, request.admission_year) from exc
    except (InvalidRuleDataError, CatalogValidationError) as exc:
        # 범위는 있는데 규칙·카탈로그 데이터가 불완전하거나 모순이다. 그 밖의 예외(코드 버그)는
        # 삼키지 않고 그대로 전파한다.
        raise _invalid_rule_data() from exc
    result.excluded_courses = sorted(
        [*result.excluded_courses, *duplicates], key=lambda notice: notice.index
    )
    return result
