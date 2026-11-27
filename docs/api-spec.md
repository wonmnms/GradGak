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
| `status` | `"met"` \| `"unmet"` \| `"pending"` | 충족 / 미충족 / 판정 보류(규칙 데이터 미완성) |
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
| `course_code` | string \| null | 학수번호(학정번호). 형식은 `학과코드(4)-난이도(1)-과목번호(4)-분반(2)`(예: `I030-1-0019-02`)이며 가운데 과목번호 4자리로 매칭한다. 형식이 다르거나 번호를 찾지 못하면 이름으로 대체하지 않고 미매칭으로 처리한다. PDF에서 못 읽었거나 사용자가 직접 추가한 과목은 `null` |
| `name` | string | 과목명 (PDF 표기 그대로) |
| `category` | string | 이수구분 (PDF 표기 그대로, 예: `전필`, `전선`) |
| `credits` | number | 학점 |
| `grade` | string \| null | 성적 (PDF 표기 그대로, 예: `A+`, `P`, `F`, `C+(삭제)`). PDF에서 성적이 빈 칸이면 `null`이며 수강 중·성적 미확정일 수 있다. 수강 예정 과목에도 `null`을 사용한다 |
| `is_retake` | bool | 재수강 여부 |

### 에러 응답

```json
{ "detail": { "code": "NO_TEXT_LAYER", "message": "PDF에서 텍스트를 읽을 수 없습니다. ..." } }
```

`code`는 프론트가 분기 처리에 쓰고, `message`는 화면에 그대로 보여줄 수 있는 문장이다. 입력 형식 오류(필드 누락·잘못된 값)는 FastAPI 기본 422 응답을 그대로 쓴다.

위 형식은 서버가 의도적으로 반환하는 에러에만 해당한다. 처리되지 않은 서버 예외(500, 평문 `Internal Server Error`)나 존재하지 않는 경로(404, `detail`이 문자열)에는 `code`가 없다.

---

## POST /transcripts/parse

KLAS 이수내역 PDF를 받아 이수과목 목록으로 변환한다. DB에 저장하지 않는다.

### 요청

`multipart/form-data`

| 필드 | 필수 | 설명 |
| --- | --- | --- |
| `file` | O | KLAS 이수내역 PDF 1개 |

파일 크기는 **10 MiB (10,485,760바이트) 이하**로 제한한다. multipart 헤더·경계 등 부가 데이터에는 최대 64 KiB를 허용하며, 전체 요청이 10 MiB + 64 KiB를 넘으면 `FILE_TOO_LARGE`를 반환한다.
업로드는 크기를 제한한 메모리에서 처리하고 PDF나 추출 결과를 파일·DB에 저장하지 않는다.
파일명·MIME 타입만으로 PDF를 판별하지 않고 PDF 시그니처와 실제 문서 열기 결과를 확인한다.

> 공학인증점검표 업로드는 MVP 범위 밖 (#28)

### 응답 200

```json
{
  "admission_year": 2024,
  "courses": [ /* Course[] */ ],
  "parse_warnings": [
    { "row": 12, "message": "학점 값을 숫자로 인식하지 못했습니다. 해당 행을 확인해주세요." }
  ]
}
```

| 필드 | 설명 |
| --- | --- |
| `admission_year` | 학번 앞 4자리로 추정한 입학년도. 못 읽으면 `null` (검수 화면에서 사용자가 입력). 학번·이름 등 다른 개인정보는 응답에 넣지 않는다 |
| `courses` | 읽은 과목 목록 |
| `parse_warnings` | 일부 행을 제대로 읽지 못한 경우의 안내. `row`는 중첩된 외곽 레이아웃 표를 제외한 표의 페이지·표 순서에서 1부터 시작하는 누적 행 번호(헤더·빈 행 포함). 경고가 있어도 나머지 과목은 반환한다 |

과목 헤더가 인식되었지만 과목이 0개인 경우에도 HTTP 200과 `courses=[]`를 반환한다.
모든 행을 인식하지 못했다면 기존 행별 경고를 유지한다. 헤더만 있거나 빈 행뿐인 표에는 첫 과목 헤더 행을 가리키는 경고를 추가한다.
HTTP 200만으로 과목 추출 성공을 판단하지 말고 빈 목록과 `parse_warnings`를 확인해야 한다.
과목 표를 찾지 못했거나 텍스트가 있는 페이지의 표를 인식하지 못한 경우에는 `400 TABLE_NOT_FOUND`다.

개인정보 노출을 막기 위해 경고와 오류에는 PDF 원문 행, 학번·이름, 파일명, 라이브러리 예외 내용을 넣지 않는다.
F·NP 성적, 빈 성적, 재수강 행과 `(삭제)` 성적 행을 모두 보존한다. 삭제 표기는 `grade` 문자열에 그대로 남기며 삭제를 재수강으로 간주하지 않는다. `is_retake`는 재수강 열의 명시적 표시만 반영한다. 과목 매칭·중복 제거·유효 취득 학점 판정은 수행하지 않는다.

### 에러

| 상태 | `code` | 상황 |
| --- | --- | --- |
| 400 | `NOT_PDF` | PDF가 아니거나 손상·암호 설정 등으로 열 수 없는 파일 |
| 400 | `NO_TEXT_LAYER` | 텍스트 레이어가 없는 PDF (예: 인쇄 기능으로 저장한 파일) — 저장 방법 안내 필요 |
| 400 | `TABLE_NOT_FOUND` | 과목 표를 찾지 못했거나, 텍스트는 있지만 표를 인식하지 못한 페이지가 있음. 마지막 합계·출력일시 전용 페이지도 예외 없이 오류 반환 |
| 413 | `FILE_TOO_LARGE` | 파일 10 MiB 또는 전체 multipart 요청 10 MiB + 64 KiB 제한 초과 |

`NO_TEXT_LAYER` 응답은 KLAS 원본 다운로드 등 텍스트를 선택·복사할 수 있는 저장본을 사용하도록 안내한다. OCR은 제공하지 않는다.

지원하는 PDF 구조·제한사항과 검증 절차는 [파서 테스트 안내](../backend/tests/README.md)를 참고한다.

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
- 세부전공필수·졸업논문·TOPCIT는 프로그램과 상관없는 공통 요건이라 한 번만 판정한다. 과목은 요청한 `program` 범위의 매칭 결과로 판정한다
- 과목 매칭과 verified 대체·인정 관계는 프로그램 범위마다 따로 적용한다. 각 `program_results` 항목은 **자기 범위**의 매칭 결과로만 총학점·과목 그룹을 판정하므로, 한 범위에서 모호하거나 찾지 못해도 다른 범위의 판정에서 과목이 빠지지 않는다
- 대체·인정은 verified 관계의 단방향 1단계만 쓴다. 대체된 필수과목은 이수로 보지만, 이수한 과목 하나는 한 그룹에서 과목 최대 1개만 채운다(대상이 여럿이어도 1개). 학점은 원래 과목으로만 센다. 원래 과목과 대체 대상을 둘 다 이수했으면 학점을 모두 인정하되 `warnings`에 확인 안내를 남긴다(한 번만 인정할지는 학부 확인 전)

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
  ],
  "excluded_courses": [
    { "index": 3, "name": "(과목명)", "reason": "성적 'F'은(는) 학점·이수로 인정하지 않았습니다." }
  ],
  "pending_data": ["program_credit_mappings_and_category_course_lists"],
  "warnings": ["규칙 데이터가 미완성이라 최종 충족으로 판정할 수 없습니다."]
}
```

> 숫자는 형식 설명용 예시이며 실제 졸업요건 값이 아니다. 실제 값은 시드 데이터(#13)에서 온다.

| 필드 | 설명 |
| --- | --- |
| `graduation_status` | 최종 판정. 하나라도 `unmet`이면 `unmet`, 아니고 하나라도 `pending`이면 `pending`, `common_requirements`·`program_results`가 **모두** `met`이고 규칙 데이터가 완성됐을 때만 `met` |
| `common_requirements` | 공통 요건. 소프트웨어전공은 세부전공필수가 없으므로 `sub_major_required` 항목 자체를 넣지 않는다 |
| `program_results` | 프로그램별 학점 요건. 공학 선택 시 `[engineering, general]` 순서로 2개, 일반 선택 시 `[general]` 1개 |
| `total` | 총 졸업학점 |
| `total`·`categories`의 숫자 | `required`·`earned`·`remaining`은 판정할 수 없으면 `null` |
| `categories` | 영역별 학점 (기초교양·균형교양·전공필수·전공선택 등 — 실제 목록은 시드 데이터 기준). 같은 과목도 프로그램에 따라 전공 학점 인정 여부가 다를 수 있다. 영역 인정 과목 목록이 없으면 `status: "pending"`이고 `reason`에 보류 사유가 있다 |
| `course_groups` | 그 프로그램에만 적용되는 "지정 과목 N개 중 M개" 요건. 형식은 `sub_major_required`와 같다. 없으면 빈 배열. 산학협력캡스톤설계1·2 중 1과목(`required_capstone`)은 공학의 `course_groups`에만 있고, 일반의 캡스톤설계 심사는 공통 요건 `thesis`로 다룬다([데이터 검증 기록](data-verification.md) 「캡스톤 적용 범위 재검토」) |
| `missing_required_courses` | 아직 듣지 않은 필수과목 |
| `unmatched_courses` | 과목 데이터와 매칭하지 못한 과목. 사유로 "찾지 못함"과 "후보가 여러 개라 확정하지 못한 모호"를 구분한다. 과목·그룹 판정에서는 빠지지만 인정 성적이면 요청 `credits`로 총학점에는 포함한다. 프로그램 범위마다 결과가 다르면 같은 (`index`, 사유)는 한 번만 넣고, 일부 프로그램에서만 나온 항목은 사유 앞에 `(공학프로그램 기준)`처럼 붙인다. `index`는 요청 `courses` 배열의 위치(0부터). 검수 화면에서 안내용 |
| `excluded_courses` | 성적(F·NP·빈 성적·`(삭제)` 등)·재수강 중복·완전히 같은 입력 행(`중복 입력`) 때문에 학점·이수에서 제외한 과목. 형식과 프로그램 기준 표기는 `unmatched_courses`와 같다 |
| `pending_data` | 규칙 데이터가 미완성이라 판정을 보류한 항목 코드 목록 |
| `warnings` | 학점 불일치·중복 확인 불가 등 안내 문장 목록. 프로그램 범위마다 달라지면 `(일반프로그램 기준)`처럼 표기한다 |

학점은 요청의 `credits`(실제 취득 학점)를 기준으로 한다. 과목 데이터의 학점과 다르면 요청 값을 쓰고 `warnings`에 안내한다.

### 에러

| 상태 | `code` | 상황 |
| --- | --- | --- |
| 400 | `UNSUPPORTED_ADMISSION_YEAR` | DB에 졸업요건이 하나도 없는 입학년도 (MVP는 2024만) |
| 400 | `UNSUPPORTED_SCOPE` | 입학년도는 있지만 선택한 프로그램·세부전공의 졸업요건 범위가 없음(메시지: 졸업요건 데이터가 없습니다) |
| 500 | `INVALID_RULE_DATA` | 범위는 있지만 규칙·과목 데이터가 불완전하거나 모순됨(공통 규칙 누락, 과목 중복 ID, 잘못된 규칙·과목 행 등). 데이터 문제이므로 `message`는 고정 문구이고 내부 정보는 넣지 않는다 |

---

## 열린 질문

구현 전에 확인해야 하는 것. 확인되면 이 섹션에서 지우고 본문에 반영한다.

- [ ] `(삭제)`가 붙은 이전 성적과 재수강 이력을 졸업요건 판정에서 어떻게 제외할지 — 파서는 원문과 모든 행을 보존한다
- [ ] F·NP 및 성적 미확정 과목을 졸업요건 판정에서 어떻게 처리할지 — 파서는 그대로 반환한다
