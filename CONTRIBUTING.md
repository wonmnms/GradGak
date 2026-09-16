# Contributing

> 이 문서는 초안이다. 팀원 각자 검토 후 필요하면 회의에서 논의하고 수정한다.

## 브랜치 전략

- `main`: 항상 배포 가능한 상태 유지. 직접 커밋 금지, PR을 통해서만 병합
- 작업 브랜치: `type/짧은-설명` 형식 (예: `feat/graduation-requirement-api`, `fix/course-search-bug`, `docs/meeting-notes`)
  - `type`은 아래 커밋 타입과 동일한 목록 사용
- 이슈 기반으로 작업할 경우 브랜치명에 이슈 번호 포함 권장: `feat/12-course-search`

## 커밋 메시지 컨벤션

[Conventional Commits](https://www.conventionalcommits.org/)를 간소화해서 사용한다. 메시지는 한국어/영어 모두 허용.

```
<type>: <description>
```

| type       | 용도                            |
| ---------- | ------------------------------- |
| `feat`     | 새로운 기능                     |
| `fix`      | 버그 수정                       |
| `docs`     | 문서 변경 (docs/, README 등)    |
| `refactor` | 동작 변화 없는 코드 개선        |
| `test`     | 테스트 추가/수정                |
| `chore`    | 빌드, 설정, 의존성 등 기타 변경 |

예: `feat: 졸업요건 판정 API 초안 추가`, `docs: 2차 회의록 작성`

## Pull Request

- PR 제목은 커밋 컨벤션과 동일한 형식 사용
- PR 설명에 변경 이유와 확인 방법(테스트 방법)을 간단히 남긴다
- 최소 1명 이상의 팀원 리뷰 승인 후 병합
- 리뷰어가 없으면 정기회의(매주 목요일) 때 같이 확인하고 병합해도 됨 — 팀 규모상 리뷰 대기로 작업이 막히지 않도록 함
- 병합 방식은 Squash merge 권장 (커밋 히스토리 단순화)

## 이슈 및 프로젝트 보드

- 작업 단위는 GitHub Issue로 등록하고, Project 보드에서 진행 상태(Todo / In Progress / Done 등)를 관리한다
- 이슈 제목은 무엇을 할지 명확히 (예: "졸업요건 데이터 모델 구현", "이수과목 검색 UI")
- 라벨 체계는 GitHub Issue/Project 구성 시(회의 안건 8번) 확정

## 학사/졸업요건 데이터 작업 시 유의사항

- project-plan.md 7번 원칙: AI를 데이터 추출 보조 도구로 쓸 수 있으나, **AI가 추출·정리한 데이터는 반드시 원본 자료와 사람이 대조 검증한 뒤에만 판정 로직에 반영**한다
- 데이터(학사 규정/교육과정)와 판정 로직은 분리해서 설계한다 (데이터 모델은 회의 결정 후 별도 공유)

## 코드 스타일 / 개발 환경

기술 스택이 아직 확정 전이라 보류. 확정 후 언어별 린터·포매터, 로컬 실행 방법을 이 섹션에 채운다.

## 회의 및 문서

- 정기회의: 매주 목요일 수업 이후 오프라인 (시험 주차·전 주차 제외)
- 회의록은 `docs/meetings/YYYY-MM-DD.md` 형식으로 작성, 양식은 `docs/meetings/template.md` 참고
- 조사/설계 초안은 `docs/drafts/`에 모은다. 이 폴더는 `.gitignore`에 등록되어 있어 **repo에 push되지 않는다** — 대신 Notion 등에 남기고, 결정된 내용만 project-plan.md/requirements.md 등 공식 문서에 반영한다
