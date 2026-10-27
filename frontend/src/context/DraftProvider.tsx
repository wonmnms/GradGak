import { useCallback, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import { DraftContext, emptyDraft } from './draftContext';
import type { DraftContextValue, DraftState } from './draftContext';

// 메모리에만 보관합니다. localStorage 등 영구 저장은 사용하지 않습니다.
export function DraftProvider({ children }: { children: ReactNode }) {
  const [draft, setDraft] = useState<DraftState>(emptyDraft);

  const setDraftField = useCallback((field: keyof DraftState, value: string) => {
    setDraft((prev) => ({ ...prev, [field]: value }));
  }, []);

  const resetDraft = useCallback(() => setDraft(emptyDraft), []);

  const value = useMemo<DraftContextValue>(
    () => ({ draft, setDraftField, resetDraft }),
    [draft, setDraftField, resetDraft],
  );

  return <DraftContext.Provider value={value}>{children}</DraftContext.Provider>;
}
