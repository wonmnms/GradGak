// /evaluate 응답 타입은 공통 API 타입(src/types/api.ts, #22)을 그대로 씁니다.
// 결과 화면에서 쓰던 이름은 별칭으로 유지하고, 화면 전용 타입만 여기에 둡니다.
export type {
  Program,
  SubMajor,
  Status as ResultStatus,
  CreditResult as CreditRequirement,
  CategoryResult as CreditCategory,
  NonCreditResult as StatusRequirement,
  GroupCourseResult as RequirementCourse,
  CourseGroupResult as CountRequirement,
  CommonRequirement,
  MissingCourse,
  ProgramResult,
  CourseNotice,
  CourseNotice as UnmatchedCourse,
  EvaluationResult,
} from '../../types/api';

/** 가상 응답 예시. pending은 지금(2024 규칙 데이터 미완성) 서버가 실제로 내는 형태입니다. */
export type MockScenario =
  'pending' | 'unmet' | 'met' | 'review' | 'program-difference' | 'thesis-unmet';
