# GradGak 프론트엔드

## 범위

GitHub #20 공통 초기 세팅과 #25 결과 화면 mock을 포함한다. React + Vite + TypeScript + CSS Modules + React Router를 사용한다. 공통 레이아웃, 버튼, 세 화면 라우트, 메모리 기반 입력 상태와 결과 화면의 가상 데이터 UI를 제공한다.

- /upload: 업로드 화면 자리와 임시 입력 상태 시연. 실제 파일 업로드·PDF 파싱은 하지 않음.
- /review: 검수·수정 화면 자리. 입력값이 화면 이동 시 유지되는지 확인 가능. 실제 이수과목 편집은 미구현.
- /results: 승인한 결과 화면의 가상 데이터 UI. 공학/일반 비교와 상태 전환을 제공하며 실제 졸업 판정은 하지 않음.
- / 및 알 수 없는 경로: 기본 화면 이동 및 404 안내.

## 실행

Node.js 24 LTS 권장, 최소 22.13.0. 이 폴더에서 npm ci 후 npm run dev. 브라우저에서 http://localhost:5173 열기. npm run build는 타입 검사 후 dist를 생성하고 npm run preview는 http://localhost:4173에서 빌드 결과를 확인한다.

## 검사

- npm run lint: ESLint
- npm run test:results: 프로그램·세부전공 인식과 API형 가상 결과 회귀 테스트 17개 (Node 기본 테스트 러너)
- npm run typecheck: TypeScript
- npm run format:check: Prettier 검사
- npm run format: 포맷 적용
- npm run build: 타입 검사 + 프로덕션 번들

## 폴더와 협업 경계

- src/components/Layout: 함께 사용하는 로고·단계 표시·본문 너비
- src/components/Button, Notice, Field: 공통 컴포넌트
- src/styles: 공통 색·간격·기본 스타일
- src/pages/UploadPage, ReviewPage: 앞쪽 화면 구현 위치
- src/pages/ResultsPage: 김세연 담당 결과 화면(#25) 구현 위치
- src/context: 화면 이동용 임시 입력 상태. 현재 string은 UI 시연용이며 API 계약이 아님
- src/api, src/types: 확정된 docs/api-spec.md를 기준으로 #22에서 공통 API 클라이언트·요청/응답 타입·mock 추가

공통 파일 변경은 서로 알려 충돌을 줄이고, 개별 화면은 자기 페이지 폴더에서 구현한다. 새로고침하면 입력값은 초기화되며 서버·브라우저 영구저장소로 보내지 않는다.

## 다음 작업

1. 병합된 공통 레이아웃·라우트 구조를 유지하며 화면별 기능을 구현한다.
2. main에 반영된 docs/api-spec.md를 기준으로 #22에서 공통 타입·클라이언트·mock을 만든다.
3. 각자 업로드(#23), 검수(#24), 결과(#25)를 구현한다.
4. #26에서 전체 흐름을 연결한다. 시뮬레이션은 Phase 2 별도 작업이다.

이번 세팅은 #21 전체 와이어프레임 확정이나 #25 구현 완료를 의미하지 않는다. 실서비스 배포 시 BrowserRouter 경로에 대해 index.html로 fallback하는 서버 설정이 필요하다.

## 결과 화면 (#25) 후속 구현

- docs/api-spec.md의 /evaluate 응답을 기준으로 graduation_status, common_requirements, program_results, unmatched_courses를 그대로 소비한다. 결과 페이지의 result.types.ts는 임시 소비 경계이며, #22 공통 타입이 생기면 import로 교체한다. 공통 API 호출 코드나 요청 DTO는 추가하지 않았다.
- 공학은 공학·일반 두 프로그램, 일반은 일반만 표시한다. 공통 요건은 한 번만 보여 주며, 프로그램별 course_groups는 응답이 있는 경우에만 표시한다. 캡스톤 소속 등 미확정 요건을 만들지 않는다.
- AI 가상 응답은 지정 5과목 중 3과목 이수 시 충족이다. SW에는 세부전공필수 항목이 없다. 선택 과목의 미이수 후보를 개별 미이수 필수과목으로 표시하지 않는다.
- 최종 판정은 서버 응답값을 사용한다. 확인 필요는 API status가 아니라 unmatched_courses가 있을 때의 표시 경고다. 과목의 0-based index는 화면에서 1번째부터 안내한다.
- 프로그램·세부전공·시나리오 선택은 예시 설정이며 원래 Context 입력을 변경하지 않는다. 빈 값이나 알 수 없는 값은 임의 추정하지 않는다.
- 다섯 시나리오: 미충족 / 충족 / 미매칭 과목 확인 / 일반 충족·공학 미충족 / 학점 충족·논문 미충족. 숫자·과목은 화면 테스트용이며 실제 학사 판정 규칙이나 실제 이수내역이 아니다.
- ResultsPage.tsx는 선택 UI와 검수 복귀, ResultsView.tsx는 응답 표시, results.presentation.ts는 표시용 함수, results.mock.ts는 가상 응답을 담당한다.
- 실제 API 호출, 로딩·오류·재시도, 검수 입력을 이용한 재판정은 #22/#26 연결 후 남은 작업이다. #25를 닫지 않는다.
