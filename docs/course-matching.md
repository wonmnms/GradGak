# 과목 매칭 서비스 (#16)

## 구현 범위와 선행 작업

2026-10-31 확인 기준 [#11](https://github.com/wonmnms/GradGak/issues/11)과 [#12](https://github.com/wonmnms/GradGak/issues/12)는 모두 open이다.
main에는 ORM 과목 모델·Alembic 마이그레이션·검증된 과목 시드가 아직 없다.
[#16](https://github.com/wonmnms/GradGak/issues/16)은 이 자료를 임의로 만들지 않고, 검증된 카탈로그 스냅샷을 입력받는 독립 서비스로 구현한다.

[PR #36](https://github.com/wonmnms/GradGak/pull/36)의 PDF 파서와 `Course` 입력 DTO를 재사용한다.
`feat/16-course-matching`은 #15 커밋 `a9c3f68`에서 분리했으며 #15 브랜치·PR에는 변경을 추가하지 않는다.
추후 #15가 병합되면 main 기준으로 #16 변경만 남는지 확인한 뒤 통합해야 한다.

현재 `/transcripts/parse`의 응답과 `/evaluate` 명세는 변경하지 않는다. 새 HTTP 엔드포인트나 졸업요건 판정도 추가하지 않는다.
매칭은 입력 과목의 정체성을 카탈로그와 연결하고 확인된 관계 후보를 전달하는 단계다. 학점 인정·중복 학점 제외·요건 충족을 판정하지 않는다.

## 입력 경계

`app/schemas/course_matching.py`의 다음 클래스는 **ORM 모델이 아닌 매칭용 DTO**다.
DB 테이블명·컬럼·식별자 타입을 확정하는 의미가 아니다.

| DTO | 의미 |
| --- | --- |
| `CatalogCourse` | `course_id`, 선택 학수번호 `course_code`, 현재 과목명 `name`만 있는 정체성 자료 |
| `CourseAlias` | 확인된 과거 과목명 `name` → `course_id`와 `source_document` |
| `CourseEquivalence` | 명시적인 `source_course_id` → `target_course_id` 관계와 `source_document` |
| `CourseCatalogSnapshot` | 과목·별칭·대체/인정 관계를 한 번에 읽은 카탈로그 |

`course_id`는 어댑터가 주는 불투명한 문자열 키다. 실제 DB가 정수나 UUID를 사용해도 어댑터에서 변환할 수 있다.
`CourseCatalogRepository.load_snapshot()`은 향후 DB 연동 지점이다. 교육과정·학과·입학년도·프로그램 등 적용 범위와 검증된 근거를 반영한 자료만 제공해야 한다.
조회 실패는 그대로 전파하며 과목 매칭 실패로 위장하지 않는다.

가상 데이터는 테스트에만 있다. 실제 과목·별칭·대체 관계는 #12에서 원본 대조와 근거 기록을 완료한 자료만 연결해야 한다.

## 매칭 정책

1. 학수번호가 있으면 앞뒤 공백만 제거해 정확히 비교한다. 대소문자·하이픈·선행 0을 바꾸지 않는다.
2. 학수번호가 없을 때만 과목명과 별칭을 조회한다. 학수번호가 있지만 찾지 못한 경우 이름으로 몰래 대체하지 않는다.
3. 이름 비교는 Unicode NFC, 대소문자 접기(casefold), 모든 공백 제거만 적용한다. 구두점·숫자는 보존한다.
4. 유사도·오타 교정·부분 문자열·로마 숫자 치환으로 추측하지 않는다.
5. 현재 이름과 별칭은 같은 후보 집합에 넣는다. 서로 다른 Course ID가 둘 이상이면 모호함으로 반환한다.
6. 같은 ID를 가리키는 중복 별칭은 후보를 중복 생성하지 않으며 근거 목록은 보존한다.
7. 학점·성적·이수구분을 이용해 모호한 과목을 임의 선택하지 않는다.

예를 들어 공백 차이는 같은 이름으로 조회할 수 있지만 `가상실습1`/`가상실습2`, `가상C`/`가상C++`는 구분한다.
서로 다른 과목의 정규화된 이름이 같으면 첫 번째 행을 택하지 않고 모든 후보를 반환한다.

## 결과와 중복

`match_courses(courses, snapshot)`은 다음 그룹을 가진 `CourseMatchingResult`를 반환한다.

| 필드 | 의미 |
| --- | --- |
| `matched` | 후보가 정확히 하나인 행과 연결된 `matched_course` |
| `unmatched` | 후보를 찾지 못한 행; 원본과 이유 유지 |
| `ambiguous` | 후보가 둘 이상인 행; 모든 후보와 근거 유지 |
| `duplicate_inputs` | 8개 입력 필드가 완전히 같은 행의 `index`와 최초 `duplicate_of` |
| `repeated_matches` | 여러 입력 행이 같은 Course ID에 연결된 경우의 전체 인덱스 |

각 행은 원본 `original`, 입력 위치 `index`, 조회 기준 `lookup`, 안전한 안내 `reason`을 가진다.
`ordered_results` 속성은 세 결과 그룹을 원래 순서대로 합쳐 모든 입력을 정확히 한 번씩 돌려준다.
정확히 중복된 입력도 버리지 않고 원래 그룹과 `duplicate_inputs`에 함께 표시한다.
학기가 다르거나 성적·재수강 표시가 다른 이력은 단순 중복 입력으로 판단하지 않는다.
`repeated_matches`는 검수용 정보이며 오류·재수강 판정이나 학점 제외 지시가 아니다.

F·NP·빈 성적·`(삭제)` 성적도 매칭 대상에서 제거하지 않는다. 입력과 카탈로그를 변경하거나 결과를 파일·DB에 저장하지 않는다.

## 별칭과 대체/인정 관계

별칭은 이전 이름에서 실제 과목을 찾는 데 사용한다. 별칭과 현재 이름이 서로 다른 과목을 가리키면 모호함이다.
대체/인정 관계는 정체성 매칭 후 `equivalence_candidates`에 **관계 후보 정보**로 제공한다.
실제로 수강한 원래 Course를 대체 Course로 바꾸거나, 두 Course의 정체성을 합치지 않는다.

- 제공된 방향의 직접 관계 1단계만 사용한다. 역방향·양방향·전이를 자동 생성하지 않는다.
- 같은 관계가 여러 근거로 제공되면 대상은 하나로 묶고 근거는 유지한다.
- 모호한 과목은 정체성이 확정되지 않았으므로 대체/인정 대상을 선택하지 않는다.
- 관계 후보를 반환했다고 학점이 인정되거나 특정 졸업요건을 충족한 것은 아니다.

카탈로그 Course ID 중복, 존재하지 않는 Course를 참조하는 별칭·관계, 자기 자신을 가리키는 대체 관계는 `CatalogValidationError`다.
같은 학수번호·이름을 가진 서로 다른 ID는 데이터 오류로 무시하지 않고 매칭의 모호함으로 다룬다.

## 호출 예시

아래는 실제 교육과정이 아닌 서비스 사용법을 위한 가상 데이터다.

```python
from app.schemas.course_matching import CatalogCourse, CourseAlias, CourseCatalogSnapshot
from app.schemas.transcripts import Course
from app.services.course_matching import match_courses

catalog = CourseCatalogSnapshot(
    courses=[CatalogCourse(course_id="fake-a", course_code="FAKE-101", name="가상새과목")],
    aliases=[CourseAlias(name="가상옛과목", course_id="fake-a", source_document="synthetic://example")],
)
inputs = [Course(year=2031, term="1", name="가상옛과목", category="전선", credits=3,
                 grade="B0", is_retake=False)]
result = match_courses(inputs, catalog)
assert result.matched[0].matched_course.course_id == "fake-a"
```

DB 연동 후에는 `match_courses_from_repository(inputs, repository)`로 요청당 스냅샷을 한 번 읽을 수 있다.

## 검증과 DB 연동 후속 작업

공개 테스트는 가상 Course 데이터만 사용한다. 학수번호가 없는 KLAS 입력 조건을 재현한 다수 행 이름 매칭도 검증하며, 실제 이수내역이나 교육과정은 테스트에 넣지 않는다.
실제 KLAS 과목을 실제 교육과정과 매칭하는 통합 검증은 #11·#12와 DB 어댑터가 준비된 후 별도로 필요하다.

1. #11의 실제 Course·Alias·Equivalence 모델, 식별자와 유일성 규칙 확정
2. #12의 과목·과거 이름·대체/인정 관계 원본 대조와 `source_document` 검증
3. 교육과정·학과·연도·프로그램별 범위를 반영하는 저장소 어댑터 구현
4. 관계의 방향·유효 기간·인정 범위 및 양방향/전이 허용 여부 확인
5. #18의 `/evaluate`에서 미매칭·모호함·중복 정보를 소비하는 방식 합의
6. 실자료 기반 통합 테스트와 DB 실패 처리 확인

`/evaluate`의 기존 `unmatched_courses[{index,name,reason}]`에는 매칭 결과를 어댑터에서 변환해 연결할 수 있으나, 이 작업에서 HTTP 응답 계약을 임의로 확장하지 않는다.
