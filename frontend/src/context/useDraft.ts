import { useContext } from 'react';
import { DraftContext } from './draftContext';
import type { DraftContextValue } from './draftContext';

export function useDraft(): DraftContextValue {
  const ctx = useContext(DraftContext);
  if (!ctx) {
    throw new Error('useDraft는 DraftProvider 안에서만 사용할 수 있습니다.');
  }
  return ctx;
}
