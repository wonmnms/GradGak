import { useCallback, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import { DraftContext, emptyDraft } from './draftContext';
import type { DraftContextValue, DraftState } from './draftContext';
import type { TranscriptParseResponse } from './transcript';

// 개인정보를 포함할 수 있는 이수내역은 페이지가 열린 동안 메모리에만 유지합니다.
export function DraftProvider({ children }: { children: ReactNode }) {
  const [draft, setDraft] = useState<DraftState>(emptyDraft);
  const [transcript, setTranscript] = useState<TranscriptParseResponse | null>(null);

  const setDraftField = useCallback((field: keyof DraftState, value: string) => {
    setDraft((prev) => ({ ...prev, [field]: value }));
  }, []);

  const resetDraft = useCallback(() => {
    setDraft(emptyDraft);
    setTranscript(null);
  }, []);

  const value = useMemo<DraftContextValue>(
    () => ({ draft, setDraftField, resetDraft, transcript, setTranscript }),
    [draft, setDraftField, resetDraft, transcript],
  );

  return <DraftContext.Provider value={value}>{children}</DraftContext.Provider>;
}
