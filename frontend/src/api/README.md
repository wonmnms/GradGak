# api

docs/api-spec.md(#40 머지 기준)의 `/transcripts/parse`, `/evaluate`를 호출하는 공통 클라이언트입니다(#22).

## 사용법

```ts
import { api, ApiError } from '../../api';

try {
  const parsed = await api.parseTranscript(file, { signal });
  const result = await api.evaluate({
    admission_year: 2024,
    program,
    sub_major,
    thesis_passed,
    topcit_taken,
    courses,
  });
} catch (error) {
  if (error instanceof ApiError) {
    // error.code: 서버 code(NO_TEXT_LAYER, UNSUPPORTED_SCOPE 등), 422는 VALIDATION_ERROR
    // error.message: 화면에 그대로 보여줄 수 있는 문장
    // error.retryable: 재시도 버튼을 보여줄지(네트워크 오류, 5xx)
  }
}
```

## mock ↔ 실제 서버 전환

`.env.example`을 `.env.local`로 복사해 값을 바꿉니다.

- `VITE_API_MODE=http`: 실제 서버(`VITE_API_BASE_URL`, 기본 `http://localhost:8000`)
- 비우거나 그 밖의 값: mock(가상 응답, 400ms 지연). 알 수 없는 값은 실제 서버로 추정하지 않습니다.

실제 서버로 붙일 때는 백엔드 CORS 설정(`CORS_ORIGINS`)에 `http://localhost:5173`이 있어야 합니다.

## 파일

- `client.ts`: `ApiClient` 인터페이스와 fetch 기반 실제 서버 클라이언트
- `errors.ts`: `ApiError`와 에러 본문 변환. 400·413·500은 `{"detail": {"code","message"}}`, 422는 FastAPI 기본 `{"detail": [...]}` 배열
- `mock.ts`: 같은 인터페이스의 가상 클라이언트. 과목·학점·요건은 모두 화면 개발용 가상 값입니다
- `config.ts`: 환경변수 해석
- `index.ts`: 화면에서 쓰는 `api` 인스턴스

테스트: `npm run test:api`
