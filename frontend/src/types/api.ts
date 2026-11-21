// docs/api-spec.md(#40 머지 기준)의 요청·응답 타입입니다.
// 백엔드 스키마: backend/app/schemas/transcripts.py, backend/app/schemas/evaluation.py

// ── 공통 값 ──────────────────────────────────────────────
export type Program = 'engineering' | 'general';
export type SubMajor = 'software' | 'ai';
/** met 충족 / unmet 미충족 / pending 판정 보류(규칙 데이터 미완성) */
export type Status = 'met' | 'unmet' | 'pending';
export type Term = '1' | '2' | 'summer' | 'winter';

/** 이수과목. /transcripts/parse 응답과 /evaluate 요청에서 같은 형식을 쓴다. */
export interface Course {
  year: number;
  term: Term;
  /** PDF에서 못 읽었거나 사용자가 직접 추가한 과목은 null */
  course_code: string | null;
  name: string;
  category: string;
  credits: number;
  /** 빈 성적(수강 중·미확정·수강 예정)은 null */
  grade: string | null;
  is_retake: boolean;
}

// ── POST /transcripts/parse ─────────────────────────────
export interface ParseWarning {
  /** 1부터 시작하는 누적 행 번호(헤더·빈 행 포함) */
  row: number;
  message: string;
}

export interface TranscriptParseResponse {
  /** 못 읽으면 null. 검수 화면에서 사용자가 입력 */
  admission_year: number | null;
  courses: Course[];
  parse_warnings: ParseWarning[];
}

export type ParseErrorCode = 'NOT_PDF' | 'NO_TEXT_LAYER' | 'TABLE_NOT_FOUND' | 'FILE_TOO_LARGE';

// ── POST /evaluate ──────────────────────────────────────
export interface EvaluateRequest {
  admission_year: number;
  program: Program;
  sub_major: SubMajor;
  thesis_passed: boolean;
  topcit_taken: boolean;
  /** 검수·수정을 마친 이수과목. 응답의 index는 이 배열의 위치(0부터) */
  courses: Course[];
}

export interface GroupCourseResult {
  course_code: string | null;
  name: string;
  completed: boolean;
}

/** "지정 과목 N개 중 M개" 요건 (세부전공필수, 프로그램별 course_groups) */
export interface CourseGroupResult {
  id: string;
  label: string;
  status: Status;
  required_count: number;
  completed_count: number;
  courses: GroupCourseResult[];
}

/** 학점이 아닌 요건 (졸업논문, TOPCIT) */
export interface NonCreditResult {
  id: string;
  label: string;
  status: Status;
}

export type CommonRequirement = CourseGroupResult | NonCreditResult;

/** 판정할 수 없으면 숫자가 null이다. */
export interface CreditResult {
  required: number | null;
  earned: number | null;
  remaining: number | null;
  status: Status;
}

export interface CategoryResult extends CreditResult {
  id: string;
  label: string;
  /** pending일 때 보류 사유 */
  reason?: string | null;
}

export interface MissingCourse {
  course_code: string | null;
  name: string;
  credits: number | null;
  category?: string | null;
}

export interface ProgramResult {
  program: Program;
  status: Status;
  total: CreditResult;
  categories: CategoryResult[];
  course_groups: CourseGroupResult[];
  missing_required_courses: MissingCourse[];
}

/**
 * 과목별 안내. index는 요청 courses 배열 위치(0부터).
 * 일부 프로그램에서만 나온 항목은 reason 앞에 "(일반프로그램 기준)" 같은 접두어가 붙는다.
 */
export interface CourseNotice {
  index: number;
  name: string;
  reason: string;
}

export interface EvaluationResult {
  graduation_status: Status;
  common_requirements: CommonRequirement[];
  /** 공학 선택 시 [engineering, general], 일반 선택 시 [general] */
  program_results: ProgramResult[];
  /** 매칭 실패 또는 후보 여러 개(모호). 인정 성적이면 총학점에는 포함된다 */
  unmatched_courses: CourseNotice[];
  /** F·NP·빈 성적·(삭제)·재수강 중복·중복 입력으로 제외한 과목 */
  excluded_courses: CourseNotice[];
  /** 판정을 보류한 규칙 데이터 항목 코드 */
  pending_data: string[];
  /** 학점 불일치, 대체 과목 중복 등 안내 문장 */
  warnings: string[];
}

export type EvaluateErrorCode =
  'UNSUPPORTED_ADMISSION_YEAR' | 'UNSUPPORTED_SCOPE' | 'INVALID_RULE_DATA';

// ── 에러 응답 ────────────────────────────────────────────
/** 400·413·500: { "detail": { "code", "message" } } */
export interface ApiErrorDetail {
  code: string;
  message: string;
}

/** 422(FastAPI 기본): { "detail": [ { loc, msg, type } ] } */
export interface ValidationErrorItem {
  loc: (string | number)[];
  msg: string;
  type: string;
}

export function isCourseGroupResult(item: CommonRequirement): item is CourseGroupResult {
  return 'required_count' in item && 'completed_count' in item && 'courses' in item;
}
