"""공식 시드가 공유하는 과목 식별. 출처는 식별 키로 사용하지 않는다."""

from sqlalchemy import select, text

from app.models import Course


def ensure_course(session, *, name, department, source_id, credits=None):
    # PostgreSQL 트랜잭션 종료까지 동시 시드의 조회-삽입을 직렬화한다.
    session.execute(text("LOCK TABLE courses IN SHARE ROW EXCLUSIVE MODE"))
    candidates = session.scalars(
        select(Course).where(
            Course.name == name,
            (Course.department == department) | Course.department.is_(None),
        )
    ).all()
    if len(candidates) > 1:
        raise ValueError(f"Ambiguous course identity: {department}/{name}")
    if candidates:
        course = candidates[0]
        if course.department is None:
            raise ValueError(f"Course department needs verification: {name}")
        if credits is not None and course.credits != credits:
            raise ValueError(f"Existing Course conflicts: {name}/credits")
        return course
    course = Course(name=name, department=department, source_id=source_id, credits=credits)
    session.add(course)
    session.flush()
    return course
