import type {
  CommonRequirement,
  CountRequirement,
  CreditRequirement,
  EvaluationResult,
  SubMajor,
} from './result.types';

export function parseSubMajor(value: string): SubMajor | null {
  const normalized = value.trim().toLowerCase().replace(/\s+/g, '');
  if (['ai', '인공지능', '인공지능전공'].includes(normalized)) return 'ai';
  if (['sw', 'software', '소프트웨어', '소프트웨어전공'].includes(normalized)) return 'software';
  return null;
}
export function hasCourseCount(item: CommonRequirement): item is CountRequirement {
  return 'required_count' in item && 'completed_count' in item && 'courses' in item;
}
export function creditProgress(total: CreditRequirement): number {
  if (!Number.isFinite(total.required) || !Number.isFinite(total.earned) || total.required <= 0)
    return 0;
  return Math.min(100, Math.max(0, Math.round((total.earned / total.required) * 100)));
}
// 판정은 응답값을 그대로 사용합니다. review는 API status가 아니라 표시 전용 상태입니다.
export function getResultSummary(result: EvaluationResult) {
  if (result.unmatched_courses.length > 0) {
    return { status: 'review' as const, label: '확인 필요', needsReview: true };
  }
  return {
    status: result.graduation_status,
    label: result.graduation_status === 'met' ? '졸업요건 충족' : '졸업요건 미충족',
    needsReview: false,
  };
}
