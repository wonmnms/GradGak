import { createContext } from 'react';

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
}

export const emptyDraft: DraftState = {
  program: '',
  subMajor: '',
  thesis: '',
  topcit: '',
};

export const DraftContext = createContext<DraftContextValue | null>(null);
