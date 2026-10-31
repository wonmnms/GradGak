# DB 개발 환경 및 실행 방법

## 준비

- Docker Desktop을 실행한다.
- 저장소 루트에서 PowerShell 터미널을 연다.
- `.env`가 없다면 `.env.example`을 복사하고 필요한 값을 설정한다.

```powershell
Copy-Item .env.example .env
```

기존 `.env`가 있다면 복사하지 않는다.

## 컨테이너 실행

```powershell
docker compose up -d --build
docker compose ps
```

## DB 테이블 생성

이미 저장소에 있는 마이그레이션을 적용한다.

```powershell
docker compose run --rm --no-deps -v "${PWD}/backend:/app" backend alembic upgrade head
```

생성되는 테이블:

- courses: 교과목
- graduation_requirements: 입학년도·프로그램·세부전공별 졸업요건
- requirement_categories: 졸업요건별 이수영역
- requirement_category_courses: 이수영역과 교과목 연결
- course_group_requirements: 지정 과목 중 최소 이수 개수
- course_group_requirement_courses: 과목 그룹과 교과목 연결
- course_aliases: 과목명 별칭
- course_equivalences: 졸업요건 범위별 방향성 있는 대체 인정
- source_documents: 자료 출처 및 조회일
- requirement_sources: 졸업요건별 자료 근거와 검증 기록
- non_credit_requirements: 졸업논문·TOPCIT 공통 규칙 정의
- alembic_version: 적용한 마이그레이션 버전

## 마이그레이션 확인

```powershell
docker compose run --rm --no-deps -v "${PWD}/backend:/app" backend alembic current
docker compose run --rm --no-deps -v "${PWD}/backend:/app" backend alembic check
```

`alembic check`에서 `No new upgrade operations detected.`가 나오면
Alembic이 비교한 DB 구조와 모델 사이에 차이가 없는 상태다.

## 개발용 가상 데이터

다음 명령어는 개발 DB에 테스트 데이터를 저장하고 테이블 4개를 연결해 조회한다.

```powershell
docker compose exec backend python -m app.seed_demo
```

2099년, TEST 프로그램, TEST_MAJOR 전공 및 TEST-DEMO-001 과목은
모두 가상 데이터다. 공식 졸업요건이나 실제 졸업 판정에 사용하지 않는다.

순차적으로 다시 실행하면 기존 데이터를 재사용한다.

## 테스트 및 코드 검사

마이그레이션을 적용한 뒤 실행한다.

```powershell
docker compose exec backend pytest -v
docker compose run --rm --no-deps -v "${PWD}/backend:/app" backend ruff check .
docker compose run --rm --no-deps -v "${PWD}/backend:/app" backend ruff format --check .
```

DB 테스트는 과목코드 중복과 존재하지 않는 졸업요건 참조가
거부되는지 확인한다. 테스트 데이터는 롤백한다.

GitHub CI에서는 별도 PostgreSQL 테스트 DB를 실행하고,
마이그레이션 적용 및 구조 비교 후 테스트한다.

## 검증된 초기 데이터 입력 및 조회

사람이 대조한 범위와 남은 항목은 [데이터 검증 기록](data-verification.md)을 따른다.

```powershell
docker compose exec backend python -m app.seed_official_credits
docker compose exec backend python -m app.seed_official_ai_group
docker compose exec backend python -m app.seed_official_common
docker compose exec backend python -m app.seed_official_engineering
docker compose exec backend python -m app.show_rules --program engineering --sub-major ai
```

과목의 미확인 학수번호·이수구분·학점은 NULL이다. NULL 학점은 0학점이 아니다.
과목명의 중의성이 발견되면 시드는 중단한다.
공학 선택 시 공학·일반 학점 규칙을 조회하며, 공통요건은 한 번만 반환한다.
이 조회 결과는 DB 내부 전달 형식이며 `/evaluate` API의 응답 DTO가 아니다.
미완성 데이터는 `data_complete: false`와 `pending_data`로 명시한다.
이 모듈은 졸업 판정을 계산하지 않는다.
관계도·조회 계약은 [DB 스키마](db-schema.md), 중간보고에 사용할 결과와 제한은
[DB 개발 현황](db-progress.md)을 참고한다.

## 새 DB에서 재현

빈 PostgreSQL DB를 향하도록 연결 정보를 설정하고 `alembic upgrade head`를 먼저 실행한다.
위 공식 데이터 시드 4개는 같은 값을 재사용하므로 순차 재실행이 가능하다.
이미 저장된 값과 충돌하면 전체 입력을 롤백하며 자동으로 덮어쓰지 않는다.
테스트는 자체 트랜잭션을 롤백하므로 실제 학사자료를 삭제하지 않는다.

## 현재 구현 범위

도메인 모델 11개, Alembic 마이그레이션, 가상·공식 초기 데이터 입력,
프로그램별 규칙 조회 및 무결성 테스트를 구현했다.
공식 초기 데이터는 사용자 대조가 끝난 학점표·인공지능 과목 그룹·공통 비학점 요건,
공학 필수 이수와 캡스톤 택1 및 수학·기초과학 하위 최소 학점이다.
전체 과목 인정표, 미확인 과목별 학점·학수번호 및 교양 세부 조건 등은 아직 보완해야 한다.
실제 졸업 판정 계산 및 API 연결은 백엔드 담당 영역이며 이번 DB 조회 모듈에 포함하지 않는다.
