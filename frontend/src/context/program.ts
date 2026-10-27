// 임시 입력과 결과 미리보기에서 공유하는 UI 타입이며 API 계약이 아닙니다.
export type DraftProgram = 'engineering' | 'general';

export function parseProgram(value: string): DraftProgram | null {
  const normalized = value.trim().toLowerCase().replace(/\s+/g, '');
  if (['일반', '일반프로그램', 'general'].includes(normalized)) return 'general';
  if (['공학', '공학프로그램', 'engineering'].includes(normalized)) return 'engineering';
  return null;
}
