# GradGak(졸업각) - 광운대학교 졸업요건 분석 및 수강계획 시뮬레이터

광운대학교 학생의 입학년도, 학과, 이수과목 등의 정보를 바탕으로 졸업요건 충족 여부를 분석하고, 부족한 요건과 향후 수강계획을 확인할 수 있는 웹 서비스이다.

## 프로젝트 목적

광운대학교의 졸업요건은 입학년도와 학과 등에 따라 달라질 수 있으며, 학생이 자신의 이수내역을 직접 확인하고 졸업 가능 여부를 판단하기에는 여러 학사 규정을 확인해야 하는 어려움이 있다.

본 프로젝트는 이러한 정보를 바탕으로 학생의 현재 졸업 진행 상황을 자동으로 분석하고, 향후 수강계획을 세우는 데 도움을 주는 것을 목표로 한다.

> 배경·목표 상세는 [docs/project-plan.md](docs/project-plan.md) 참고.

## 주요 기능

> 아래는 요약이며, 최신 Phase별 상세 범위는 [docs/project-plan.md](docs/project-plan.md) 5번이 기준이다. 두 문서가 어긋나면 project-plan.md를 따른다.

### MVP

- 프로그램(공학/일반)·세부전공 선택
- KLAS 이수내역 PDF 업로드 및 이수과목 검수·수정
- 졸업학점 계산
- 졸업요건 충족 여부 분석
- 부족한 학점 및 요건 표시
- 필수 미이수 과목 안내

### 향후 기능

- 학기별 개설과목 반영
- 선수과목 관계 반영
- 수강계획 시뮬레이션
- 다음 학기 수강과목 추천
- 복수전공 및 부전공 시뮬레이션
- 졸업을 위한 최적 수강계획 탐색

## 기술 스택

> 전체 스택 확정. (Frontend는 프론트 담당(김세연·배준경) 논의로 결정)

### Frontend

- React
- Vite
- TypeScript
- CSS Modules (스타일)
- React Router (화면 이동)

### Backend

- Python
- FastAPI

### Database

- PostgreSQL
- SQLAlchemy / Alembic (ORM·마이그레이션)

### Data Processing

- httpx / BeautifulSoup (HTML 수집)
- pdfplumber / PyMuPDF (PDF 수집)
- Playwright (로그인이 필요한 경우에만 조건부 사용)

### Test

- pytest (백엔드 판정 로직)

### 최적화

- Phase 3에서 검토 (규칙 기반 필터링 우선, OR-Tools는 현재 스택에 미포함)

## 프로젝트 구조

```text
project-root/
├── README.md
├── CONTRIBUTING.md
├── docs/
│   ├── project-plan.md
│   ├── requirements.md
│   └── api-spec.md
├── frontend/
├── backend/
└── ...
```

## 팀원

| 이름   | 역할     |
| ------ | -------- |
| 최원용 | Backend  |
| 김남주 | DB       |
| 박준영 | Backend  |
| 김세연 | Frontend |
| 배준경 | Frontend |

## 개발 환경

### 프론트엔드 (React + Vite)

Node.js 24 LTS 권장 (최소 22.13.0). 저장소 루트에서:

```bash
cd frontend
npm ci
npm run dev
```

http://localhost:5173 에서 확인한다. 기본 경로는 /upload이며 /review, /results로 연결된다.
현재는 공통 화면 틀·라우팅과 결과 화면의 가상 데이터 UI를 구현했으며, 실제 PDF 파싱·졸업 판정 API는 연결하지 않았다.
입력 상태는 메모리에만 보관되어 화면 이동 시 유지되고 새로고침 시 초기화된다.

검증: `npm run lint`, `npm run build`, `npm run format:check`.
폴더 구조·협업 경계·후속 작업은 [frontend/README.md](frontend/README.md)를 참고한다.

### 백엔드 + DB (Docker Compose)

백엔드(FastAPI)와 PostgreSQL은 docker-compose로 로컬 실행한다.
(프론트엔드(React + Vite)는 컨테이너에 포함하지 않고 위 방법으로 별도 실행)

1. 저장소 루트의 `.env.example`을 복사해 `.env` 생성 (필요시 값 수정)

   ```bash
   cp .env.example .env
   ```

2. 컨테이너 실행

   ```bash
   docker-compose up --build
   ```

3. 정상 기동 확인: http://localhost:8000/health → `{"status": "ok"}`
   (DB 연결까지 확인하려면 http://localhost:8000/health/db)

4. 종료: `docker-compose down` (DB 데이터까지 삭제하려면 `docker-compose down -v`)

### 백엔드 테스트·린트

컨테이너가 실행 중인 상태에서:

```bash
docker-compose exec backend pytest
docker-compose exec backend ruff check .
docker-compose exec backend ruff format .
```

> 소스 코드(`backend/app`, `backend/tests`)는 컨테이너에 마운트되어 있어 수정하면 바로 반영된다. `requirements.txt`나 `pyproject.toml`을 바꿨다면 `docker-compose up --build`로 다시 빌드한다.
>
> CORS 허용 주소는 기본값이 Vite 개발 서버(`http://localhost:5173`)이며, 바꾸려면 `.env`에 `CORS_ORIGINS`(쉼표 구분)를 설정한다.
>
### 백엔드 로컬 테스트 (Python 3.12)

Docker 없이 테스트하려면 저장소 루트에서 가상환경을 만든다. 아래는 PowerShell 기준이다.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
cd backend
..\.venv\Scripts\python.exe -m pytest
..\.venv\Scripts\python.exe -m ruff check .
..\.venv\Scripts\python.exe -m ruff format --check .
```

테스트와 PDF 파싱 API는 DB 연결 없이 실행할 수 있다. `/health/db` 확인에는 PostgreSQL이 필요하다.
API 서버는 `backend`에서 `..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload`로 실행하며, 요청 형식은 `/docs`에서 확인한다.
Alembic 마이그레이션 사용법은 추후 추가한다([#11](https://github.com/wonmnms/GradGak/issues/11)).

### KLAS PDF 파서 검증 상태

`POST /transcripts/parse`는 KLAS 이수내역의 학기별 구획과 과목 표를 읽고, 페이지 간 연속·반복 헤더를 처리한다.
빈 성적은 `null`, 재수강 여부는 명시된 표시로 반환하며 `(삭제)`가 붙은 성적과 F·NP도 원문대로 보존한다.
텍스트를 읽을 수 없는 PDF는 OCR 없이 `NO_TEXT_LAYER`로 안내한다.

제공된 실제 변환본과 직접인쇄본은 로컬에서만 검증한다. PDF와 과목별 기대·추출 JSON은 저장소에 포함하지 않는다.
공개 테스트는 가상의 과목과 성적으로 만든 합성 자료를 사용하고, 실제 샘플 검증은 환경변수로 명시적으로 실행한다.
지원 구조와 로컬 검증 방법은 [파서 테스트 안내](backend/tests/README.md), 요청·응답은 [API 명세](docs/api-spec.md#post-transcriptsparse)를 참고한다.
검증한 저장 형식과 다른 PDF는 별도 확인이 필요하다.

## License

이 프로젝트는 [MIT License](LICENSE)를 따른다.
