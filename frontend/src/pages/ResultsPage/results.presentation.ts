import type {
  CommonRequirement,
  CountRequirement,
  CreditRequirement,
  EvaluationResult,
  ProgramResult,
  ResultStatus,
  SubMajor,
} from './result.types';

export const statusLabels: Record<ResultStatus, string> = {
  met: '충족',
  unmet: '미충족',
  pending: '판정 보류',
};

export function parseSubMajor(value: string): SubMajor | null {
  const normalized = value.trim().toLowerCase().replace(/\s+/g, '');
  if (['ai', '인공지능', '인공지능전공'].includes(normalized)) return 'ai';
  if (['sw', 'software', '소프트웨어', '소프트웨어전공'].includes(normalized)) return 'software';
  return null;
}
export function hasCourseCount(item: CommonRequirement): item is CountRequirement {
  return 'required_count' in item && 'completed_count' in item && 'courses' in item;
}
/** 판정할 수 없는 숫자(null)는 '—'로 표시합니다. */
export function formatCredit(value: number | null): string {
  return value === null || !Number.isFinite(value) ? '—' : String(value);
}
export function creditProgress(total: CreditRequirement): number {
  const { required, earned } = total;
  if (required === null || earned === null) return 0;
  if (!Number.isFinite(required) || !Number.isFinite(earned) || required <= 0) return 0;
  return Math.min(100, Math.max(0, Math.round((earned / required) * 100)));
}
export function progressLabel(total: CreditRequirement): string {
  if (total.required === null || total.earned === null) return '총학점 이수율 —';
  return '총학점 기준 ' + creditProgress(total) + '% 이수';
}
/**
 * missing_required_courses를 확정된 전체 목록으로 보면 안 되는지.
 * 서버는 과목 그룹에서만 미이수 필수과목을 계산하고, 영역 과목 목록이 없으면 영역을 pending으로 둡니다.
 * 프로그램 status는 unmet이 우선이라 pending을 가릴 수 있어 영역·pending_data·전체 판정을 직접 봅니다.
 */
export function isMissingListUnsettled(program: ProgramResult, result: EvaluationResult): boolean {
  return (
    result.graduation_status === 'pending' ||
    program.categories.some((category) => category.status === 'pending') ||
    result.pending_data.length > 0
  );
}
export function remainingLabel(total: CreditRequirement): string {
  if (total.remaining === null) return '부족 학점 판정 보류';
  return total.remaining > 0 ? total.remaining + '학점 부족' : '부족 학점 없음';
}
const summaryLabels: Record<ResultStatus, string> = {
  met: '졸업요건 충족',
  unmet: '졸업요건 미충족',
  pending: '졸업요건 판정 보류',
};
// 판정은 응답값을 그대로 사용합니다. review는 API status가 아니라 표시 전용 상태입니다.
export function getResultSummary(result: EvaluationResult) {
  if (result.unmatched_courses.length > 0) {
    return { status: 'review' as const, label: '확인 필요', needsReview: true };
  }
  return {
    status: result.graduation_status,
    label: summaryLabels[result.graduation_status],
    needsReview: false,
  };
}
