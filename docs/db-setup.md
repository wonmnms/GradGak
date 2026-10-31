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

## 현재 구현 범위

모델 4개, 초기 마이그레이션, 가상 데이터 저장·연결 조회,
중복 및 외래키 제약조건 테스트를 구현했다.

공식 졸업요건 데이터 입력과 실제 졸업 판정 기능은
이번 DB 구현 결과에 포함되지 않는다.