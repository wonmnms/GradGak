import { useId } from 'react';
import { useDraft } from '../../context/useDraft';
import { parseProgram } from '../../context/program';
import type { DraftState } from '../../context/draftContext';
import styles from './Field.module.css';

const fields: { key: keyof DraftState; label: string }[] = [
  { key: 'program', label: '프로그램(공학/일반)' },
  { key: 'subMajor', label: '세부전공(SW/AI)' },
  { key: 'thesis', label: '졸업논문·작품 통과 여부' },
  { key: 'topcit', label: 'TOPCIT 응시 여부' },
];

// 임시 입력 필드입니다. 값은 메모리(Context)에만 보관되며 서버로 전송되지 않습니다.
export default function DraftFields() {
  const { draft, setDraftField } = useDraft();
  const baseId = useId();
  const program = parseProgram(draft.program);
  const invalidProgram = draft.program.trim() !== '' && program === null;

  return (
    <div>
      {fields.map(({ key, label }) => {
        const id = `${baseId}-${key}`;
        return (
          <div className={styles.field} key={key}>
            <label htmlFor={id}>{label}</label>
            {key === 'program' ? (
              <>
                <select
                  id={id}
                  className={styles.input}
                  value={program === 'engineering' ? '공학' : program === 'general' ? '일반' : ''}
                  aria-invalid={invalidProgram || undefined}
                  aria-describedby={invalidProgram ? id + '-error' : undefined}
                  onChange={(e) => setDraftField('program', e.target.value)}
                >
                  <option value="">프로그램을 선택하세요</option>
                  <option value="공학">공학</option>
                  <option value="일반">일반</option>
                </select>
                {invalidProgram && (
                  <p id={id + '-error'} role="alert">
                    기존 프로그램 값을 확인할 수 없습니다. 다시 선택해 주세요.
                  </p>
                )}
              </>
            ) : (
              <input
                id={id}
                className={styles.input}
                type="text"
                autoComplete="off"
                value={draft[key]}
                onChange={(e) => setDraftField(key, e.target.value)}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}
