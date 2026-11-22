import type {
  CommonRequirement,
  CountRequirement,
  CreditRequirement,
  EvaluationResult,
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
