# GradGak(졸업각) - 광운대학교 졸업요건 분석 및 수강계획 시뮬레이터

광운대학교 학생의 입학년도, 학과, 이수과목 등의 정보를 바탕으로 졸업요건 충족 여부를 분석하고, 부족한 요건과 향후 수강계획을 확인할 수 있는 웹 서비스이다.

## 프로젝트 목적

광운대학교의 졸업요건은 입학년도와 학과 등에 따라 달라질 수 있으며, 학생이 자신의 이수내역을 직접 확인하고 졸업 가능 여부를 판단하기에는 여러 학사 규정을 확인해야 하는 어려움이 있다.

본 프로젝트는 이러한 정보를 바탕으로 학생의 현재 졸업 진행 상황을 자동으로 분석하고, 향후 수강계획을 세우는 데 도움을 주는 것을 목표로 한다.

> 배경·목표 상세는 [docs/project-plan.md](docs/project-plan.md) 참고.

## 주요 기능

> 아래는 요약이며, 최신 Phase별 상세 범위는 [docs/project-plan.md](docs/project-plan.md) 5번이 기준이다. 두 문서가 어긋나면 project-plan.md를 따른다.

### MVP

- 입학년도 및 학과 입력
- 이수과목 입력 및 관리
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

> 2차 회의(2026-09-17)에서 Frontend를 제외한 나머지 스택을 확정했다. Frontend는 아직 미정(담당자 재량, Action Item으로 후보 조사 중).

### Frontend

- 미정 (담당자 재량)

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
│   └── meetings/
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

개발 환경 및 실행 방법은 프로젝트의 기술 스택이 확정된 후 추가한다.

## License

프로젝트 라이선스는 팀 논의 후 결정한다.
