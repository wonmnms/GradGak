import { createContext } from 'react';
import type { TranscriptParseResponse } from './transcript';

export interface DraftState {
  program: string;
  subMajor: string;
  thesis: string;
  topcit: string;
}

export interface DraftContextValue {
  draft: DraftState;
  setDraftField: (field: keyof DraftState, value: string) => void;
  resetDraft: () => void;
  transcript: TranscriptParseResponse | null;
  setTranscript: (value: TranscriptParseResponse | null) => void;
}

export const emptyDraft: DraftState = {
  program: '',
  subMajor: '',
  thesis: '',
  topcit: '',
};

export const DraftContext = createContext<DraftContextValue | null>(null);
