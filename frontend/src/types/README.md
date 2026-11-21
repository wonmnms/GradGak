# types

- `api.ts`: docs/api-spec.md(#40 머지 기준)의 요청·응답 타입(#22). 백엔드 스키마 `backend/app/schemas/transcripts.py`, `evaluation.py`와 같은 형식입니다.
  - `status`는 `met` / `unmet` / `pending`. 지금 2024 데이터는 규칙이 미완성이라 최종 결과가 항상 `pending`입니다.
  - `total`·`categories`의 `required`·`earned`·`remaining`은 판정할 수 없으면 `null`입니다.
  - `unmatched_courses`·`excluded_courses`의 `index`는 요청 `courses` 배열 위치(0부터)라 검수 화면 행과 연결할 수 있습니다.
- 화면 이동용 임시 입력 상태 타입은 `context/draftContext.ts`에 있습니다.
