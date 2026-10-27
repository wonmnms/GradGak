# GradGak 프론트엔드

## 범위

GitHub #20 공통 초기 세팅이다. React + Vite + TypeScript + CSS Modules + React Router를 사용한다. 공통 레이아웃, 버튼, 세 화면 라우트, 메모리 기반 입력 상태와 결과 화면의 가상 데이터 UI를 제공한다.

- /upload: 업로드 화면 자리와 임시 입력 상태 시연. 실제 파일 업로드·PDF 파싱은 하지 않음.
- /review: 검수·수정 화면 자리. 입력값이 화면 이동 시 유지되는지 확인 가능. 실제 이수과목 편집은 미구현.
- /results: 승인한 결과 화면의 가상 데이터 UI. 공학/일반 비교와 상태 전환을 제공하며 실제 졸업 판정은 하지 않음.
- / 및 알 수 없는 경로: 기본 화면 이동 및 404 안내.

## 실행

Node.js 24 LTS 권장, 최소 22.13.0. 이 폴더에서 npm ci 후 npm run dev. 브라우저에서 http://localhost:5173 열기. npm run build는 타입 검사 후 dist를 생성하고 npm run preview는 http://localhost:4173에서 빌드 결과를 확인한다.

## 검사

- npm run lint: ESLint
- npm run test:results: 프로그램 인식·가상 결과 회귀 테스트 7개 (Node 기본 테스트 러너)
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
- src/api, src/types: #9 합의 후 #22에서 API 클라이언트·요청/응답 타입·mock 추가

공통 파일 변경은 서로 알려 충돌을 줄이고, 개별 화면은 자기 페이지 폴더에서 구현한다. 새로고침하면 입력값은 초기화되며 서버·브라우저 영구저장소로 보내지 않는다.

## 다음 작업

1. 공통 레이아웃·라우트 구조를 팀원이 리뷰한다.
2. #9의 요청/응답 예시를 합의한 뒤 #22에서 타입과 mock을 만든다.
3. 각자 업로드(#23), 검수(#24), 결과(#25)를 구현한다.
4. #26에서 전체 흐름을 연결한다. 시뮬레이션은 Phase 2 별도 작업이다.

이번 세팅은 #21 전체 와이어프레임 확정이나 #25 구현 완료를 의미하지 않는다. 실서비스 배포 시 BrowserRouter 경로에 대해 index.html로 fallback하는 서버 설정이 필요하다.
