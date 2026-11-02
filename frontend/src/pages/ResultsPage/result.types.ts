// docs/api-spec.md (2026-10-29)의 /evaluate 응답을 소비하는 결과 화면 경계 타입입니다.
// 공통 API 타입/호출 함수(#22)가 추가되면 이 타입을 해당 모듈의 import로 대체합니다.
export type { DraftProgram as Program } from '../../context/program';
import type { DraftProgram as Program } from '../../context/program';

export type SubMajor = 'software' | 'ai';
export type ResultStatus = 'met' | 'unmet';
export type MockScenario = 'unmet' | 'met' | 'review' | 'program-difference' | 'thesis-unmet';

export interface CreditRequirement {
  required: number;
  earned: number;
  remaining: number;
  status: ResultStatus;
}
export interface CreditCategory extends CreditRequirement {
  id: string;
  label: string;
}
export interface StatusRequirement {
  id: string;
  label: string;
  status: ResultStatus;
}
export interface RequirementCourse {
  course_code: string | null;
  name: string;
  completed: boolean;
}
export interface CountRequirement extends StatusRequirement {
  required_count: number;
  completed_count: number;
  courses: RequirementCourse[];
}
export type CommonRequirement = StatusRequirement | CountRequirement;
export interface MissingCourse {
  course_code: string | null;
  name: string;
  credits: number;
  category: string;
}
export interface ProgramResult {
  program: Program;
  status: ResultStatus;
  total: CreditRequirement;
  categories: CreditCategory[];
  course_groups: CountRequirement[];
  missing_required_courses: MissingCourse[];
}
export interface UnmatchedCourse {
  index: number;
  name: string;
  reason: string;
}
export interface EvaluationResult {
  graduation_status: ResultStatus;
  common_requirements: CommonRequirement[];
  program_results: ProgramResult[];
  unmatched_courses: UnmatchedCourse[];
}
