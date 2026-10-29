// 화면 전용 모델입니다. 백엔드 API DTO가 아니며 #9/#22 합의 후 변환 계층을 연결합니다.
export type { DraftProgram as Program } from '../../context/program';
import type { DraftProgram as Program } from '../../context/program';
export type ResultStatus = 'met' | 'unmet' | 'review';
export type MockScenario = 'unmet' | 'met' | 'review' | 'program-difference' | 'thesis-unmet';
export interface CreditRequirement {
  id: string;
  label: string;
  required: number;
  earned: number;
  remaining: number;
  status: ResultStatus;
}
export interface SpecialRequirement {
  id: string;
  label: string;
  status: ResultStatus;
  detail?: string;
}
export interface MissingCourse {
  id: string;
  name: string;
  credit: number;
  category: string;
}
export interface ProgramResult {
  program: Program;
  title: string;
  status: ResultStatus;
  total: CreditRequirement;
  categories: CreditRequirement[];
  specialRequirements: SpecialRequirement[];
  missingCourses: MissingCourse[];
}
