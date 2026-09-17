# Contributing

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

- AI 활용·데이터/로직 분리 원칙은 [project-plan.md](docs/project-plan.md) 7번을 따른다 (데이터 모델은 회의 결정 후 별도 공유)

## 코드 스타일 / 개발 환경

기술 스택이 아직 확정 전이라 보류. 확정 후 언어별 린터·포매터, 로컬 실행 방법을 이 섹션에 채운다.

## 회의 및 문서

- 정기회의: 매주 목요일 수업 이후 오프라인 (시험 주차·전 주차 제외)
- 회의록은 `docs/meetings/YYYY-MM-DD.md` 형식으로 작성, 양식은 `docs/meetings/template.md` 참고
- `project-plan.md`(전략: 배경·목표·Phase 로드맵·개발 원칙)와 `requirements.md`(상세 기능/데이터 요구사항)는 역할이 다르다. 같은 내용을 양쪽에 다시 쓰지 말고, 한쪽에만 쓰고 다른 쪽에서는 링크로 참조한다
- 조사/설계 초안은 repo가 아니라 Notion에서 관리한다. 결정된 내용만 project-plan.md/requirements.md 등 공식 문서에 반영한다
