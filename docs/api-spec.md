# API 명세

> 이 문서는 MVP(Phase 1) 백엔드 API의 **요청/응답 형식**을 다룬다. 프론트(#22 mock 포함)와 백엔드(#15, #18)는 이 문서를 기준으로 구현하고, 구현 후에는 FastAPI 자동 문서(`/docs`)가 실제 동작 기준이 되며, 구현 중 형식이 바뀌면 이 문서도 같이 갱신한다.

## 공통

- Base URL (로컬): `http://localhost:8000`
- 로그인 없음. 서버는 사용자 이수내역을 저장하지 않는다 — 업로드한 PDF와 요청 데이터는 응답 후 폐기
- 요청/응답 본문은 JSON (`/transcripts/parse` 요청만 `multipart/form-data`)
- 필드명은 `snake_case`

### 공통 값

| 이름 | 값 | 비고 |
| --- | --- | --- |
| `program` | `"engineering"` \| `"general"` | 공학 / 일반 |
| `sub_major` | `"software"` \| `"ai"` | 소프트웨어전공 / 인공지능전공 |
| `status` | `"met"` \| `"unmet"` | 충족 / 미충족 |
| `term` | `"1"` \| `"2"` \| `"summer"` \| `"winter"` | 1학기 / 2학기 / 여름 / 겨울 계절학기 |

### 이수과목 (`Course`)

`/transcripts/parse` 응답과 `/evaluate` 요청에서 같은 형식을 쓴다. 사용자가 검수 화면에서 수정·추가한 과목도 이 형식으로 보낸다.

```json
{
  "year": 2024,
  "term": "1",
  "course_code": "(학수번호)",
  "name": "리눅스활용실습",
  "category": "전필",
  "credits": 3,
  "grade": "A0",
  "is_retake": false
}
```

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `year` | int | 수강 연도 (예: `2024`. 학년이 아님) |
| `term` | string | 위 `term` 값 |
| `course_code` | string \| null | 학수번호. PDF에서 못 읽었거나 사용자가 직접 추가한 과목은 `null` |
| `name` | string | 과목명 (PDF 표기 그대로) |
| `category` | string | 이수구분 (PDF 표기 그대로, 예: `전필`, `전선`) |
| `credits` | number | 학점 |
| `grade` | string \| null | 성적 (PDF 표기 그대로, 예: `A+`, `P`, `F`). `null`은 수강 예정 과목 — Phase 2 시뮬레이션에서 앞으로 들을 과목을 추가할 때 사용 |
| `is_retake` | bool | 재수강 여부 |

> 위 예시는 형식 설명용이다. 학수번호 실제 형식은 PDF 확인 후 채운다(아래 열린 질문).

### 에러 응답

```json
{ "detail": { "code": "NO_TEXT_LAYER", "message": "PDF에서 텍스트를 읽을 수 없습니다. ..." } }
```

`code`는 프론트가 분기 처리에 쓰고, `message`는 화면에 그대로 보여줄 수 있는 문장이다. 입력 형식 오류(필드 누락·잘못된 값)는 FastAPI 기본 422 응답을 그대로 쓴다.

---

## POST /transcripts/parse

KLAS 이수내역 PDF를 받아 이수과목 목록으로 변환한다. DB에 저장하지 않는다.

### 요청

`multipart/form-data`

| 필드 | 필수 | 설명 |
| --- | --- | --- |
| `file` | O | KLAS 이수내역 PDF 1개 |

> 공학인증점검표 업로드는 MVP 범위 밖 (#28)

### 응답 200

```json
{
  "admission_year": 2024,
  "courses": [ /* Course[] */ ],
  "parse_warnings": [
    { "row": 12, "message": "학점 값을 숫자로 인식하지 못했습니다. 원문: 'ㅁ학점'" }
  ]
}
```

| 필드 | 설명 |
| --- | --- |
| `admission_year` | 학번 앞 4자리로 추정한 입학년도. 못 읽으면 `null` (검수 화면에서 사용자가 입력). 학번·이름 등 다른 개인정보는 응답에 넣지 않는다 |
| `courses` | 읽은 과목 목록 |
| `parse_warnings` | 일부 행을 제대로 읽지 못한 경우의 안내. `row`는 PDF 표 기준 행 번호(1부터). 경고가 있어도 나머지 과목은 반환한다 |

### 에러

| 상태 | `code` | 상황 |
| --- | --- | --- |
| 400 | `NOT_PDF` | PDF 파일이 아님 |
| 400 | `NO_TEXT_LAYER` | 텍스트 레이어가 없는 PDF (예: 인쇄 기능으로 저장한 파일) — 저장 방법 안내 필요 |
| 400 | `TABLE_NOT_FOUND` | 이수내역 표를 찾지 못함 (다른 문서를 올린 경우 등) |
| 413 | `FILE_TOO_LARGE` | 파일 크기 제한 초과 (제한 값은 #15에서 결정) |

---

## POST /evaluate

이수과목과 사용자 입력을 받아 졸업요건 충족 여부를 판정한다. 판정은 DB의 규칙 데이터로만 계산한다(AI 사용 안 함). 시뮬레이션(Phase 2)도 과목을 추가해 이 API를 다시 호출하는 방식으로 처리한다.

### 요청

```json
{
  "admission_year": 2024,
  "program": "engineering",
  "sub_major": "ai",
  "thesis_passed": false,
  "topcit_taken": true,
  "courses": [ /* Course[] */ ]
}
```

| 필드 | 설명 |
| --- | --- |
| `admission_year` | 입학년도. MVP는 `2024`만 지원하므로 프론트는 입력칸 없이 고정값을 보내도 된다. 지원 범위를 넓힐 때 요청 형식을 바꾸지 않으려고 미리 둔 필드 |
| `program` | 공학 / 일반 |
| `sub_major` | 소프트웨어 / 인공지능 |
| `thesis_passed` | 졸업논문(작품) '가' 판정 여부 — PDF에 없는 정보라 사용자가 입력 |
| `topcit_taken` | TOPCIT 응시 여부 — 사용자 입력 |
| `courses` | 검수·수정을 마친 이수과목 |

### 판정 범위

- `program: "engineering"` → **공학 + 일반** 학점 요건을 모두 판정한다. 졸업하려면 둘 다 충족해야 한다
- `program: "general"` → **일반** 학점 요건만 판정한다
- 세부전공필수·졸업논문·TOPCIT는 프로그램과 상관없는 공통 요건이라 한 번만 판정한다

### 응답 200

```json
{
  "graduation_status": "unmet",
  "common_requirements": [
    {
      "id": "sub_major_required",
      "label": "세부전공필수",
      "status": "unmet",
      "required_count": 3,
      "completed_count": 1,
      "courses": [
        { "course_code": "...", "name": "인공지능", "completed": true },
        { "course_code": "...", "name": "기계학습", "completed": false }
      ]
    },
    { "id": "thesis", "label": "졸업논문(작품) '가' 판정", "status": "unmet" },
    { "id": "topcit", "label": "TOPCIT 응시", "status": "met" }
  ],
  "program_results": [
    {
      "program": "engineering",
      "status": "unmet",
      "total": { "required": 130, "earned": 98, "remaining": 32, "status": "unmet" },
      "categories": [
        { "id": "major_required", "label": "전공필수", "required": 18, "earned": 12, "remaining": 6, "status": "unmet" }
      ],
      "course_groups": [],
      "missing_required_courses": [
        { "course_code": "...", "name": "...", "credits": 3, "category": "전공필수" }
      ]
    },
    { "program": "general", "...": "engineering과 같은 구조" }
  ],
  "unmatched_courses": [
    { "index": 7, "name": "(과목명)", "reason": "과목 데이터에서 찾지 못했습니다." }
  ]
}
```

> 숫자는 형식 설명용 예시이며 실제 졸업요건 값이 아니다. 실제 값은 시드 데이터(#13)에서 온다.

| 필드 | 설명 |
| --- | --- |
| `graduation_status` | 최종 판정. `common_requirements`와 `program_results`가 **모두** `met`일 때만 `met` |
| `common_requirements` | 공통 요건. 소프트웨어전공은 세부전공필수가 없으므로 `sub_major_required` 항목 자체를 넣지 않는다 |
| `program_results` | 프로그램별 학점 요건. 공학 선택 시 `[engineering, general]` 순서로 2개, 일반 선택 시 `[general]` 1개 |
| `total` | 총 졸업학점 |
| `categories` | 영역별 학점 (기초교양·균형교양·전공필수·전공선택 등 — 실제 목록은 시드 데이터 기준). 같은 과목도 프로그램에 따라 전공 학점 인정 여부가 다를 수 있다 |
| `course_groups` | 그 프로그램에만 적용되는 "지정 과목 N개 중 M개" 요건. 형식은 `sub_major_required`와 같다. 없으면 빈 배열 |
| `missing_required_courses` | 아직 듣지 않은 필수과목 |
| `unmatched_courses` | 과목 데이터와 매칭하지 못해 판정에서 빠진 과목. `index`는 요청 `courses` 배열의 위치(0부터). 검수 화면에서 안내용 |

### 에러

| 상태 | `code` | 상황 |
| --- | --- | --- |
| 400 | `UNSUPPORTED_ADMISSION_YEAR` | 지원하지 않는 입학년도 (MVP는 2024만) |

---

## 열린 질문

구현 전에 확인해야 하는 것. 확인되면 이 섹션에서 지우고 본문에 반영한다.

- [ ] KLAS 이수내역 PDF에 **학수번호**가 나오는지 — 없으면 과목 매칭(#16)을 과목명으로만 해야 함
- [ ] KLAS PDF의 학기 표기 형식(계절학기 포함)이 위 `term` 값으로 변환 가능한지
- [ ] 재수강 시 이전 성적 행이 PDF에 같이 나오는지, 나온다면 판정에서 어떻게 제외할지
- [ ] F·NP 과목을 `courses`에 포함해서 보낼지(백엔드가 제외) 파싱 단계에서 뺄지 — 현재 안: 파싱은 그대로 반환하고 판정에서 제외
- [ ] PDF의 학점과 과목 데이터(DB)의 학점이 다를 때 어느 쪽을 기준으로 판정할지 — 현재 안: 요청의 `credits`(실제 취득 학점) 사용
- [ ] 산학협력캡스톤설계1/2 중 1과목 요건이 공통 요건인지 공학 전용인지 — 위치(`common_requirements` / `course_groups`)가 달라짐
