import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Button from '../../components/Button/Button';
import { useDraft } from '../../context/useDraft';
import { parseProgram } from '../../context/program';
import { getMockResults } from './results.mock';
import { parseSubMajor } from './results.presentation';
import ResultsView from './ResultsView';
import type { MockScenario, Program, SubMajor } from './result.types';
import styles from './ResultsPage.module.css';

export default function ResultsPage() {
  const navigate = useNavigate();
  const { draft } = useDraft();
  const [program, setProgram] = useState<Program | ''>(() => parseProgram(draft.program) ?? '');
  const [subMajor, setSubMajor] = useState<SubMajor | ''>(
    () => parseSubMajor(draft.subMajor) ?? '',
  );
  const [scenario, setScenario] = useState<MockScenario>('unmet');
  const result = program && subMajor ? getMockResults(scenario, program, subMajor) : null;
  const editCourses = () => navigate('/review');
  return (
    <div className={styles.page}>
      <div className={styles.intro}>
        <p className={styles.eyebrow}>졸업요건 판정 결과 · 화면 개발용</p>
        <h1>졸업까지 무엇이 남았을까요?</h1>
        <p className={styles.description}>부족한 학점과 아직 충족하지 못한 요건을 확인하세요.</p>
      </div>
      <aside className={styles.demoNotice} aria-label="가상 데이터 안내">
        <strong>가상 데이터 미리보기</strong>
        <p>
          아래 학점·과목·요건은 모두 화면 개발용 예시입니다. 실제 광운대 졸업기준이나 본인의
          이수내역이 아니며, 검수 화면의 입력값으로 계산한 결과도 아닙니다.
        </p>
      </aside>
      <div className={styles.toolbar}>
        <h2>예시 결과 설정</h2>
        <div className={styles.controls}>
          <label>
            프로그램 보기
            <select
              value={program}
              onChange={(event) => setProgram(parseProgram(event.target.value) ?? '')}
            >
              <option value="">프로그램을 선택하세요</option>
              <option value="engineering">공학</option>
              <option value="general">일반</option>
            </select>
          </label>
          <label>
            예시 세부전공
            <select
              value={subMajor}
              onChange={(event) => setSubMajor(parseSubMajor(event.target.value) ?? '')}
            >
              <option value="">세부전공을 선택하세요</option>
              <option value="ai">인공지능전공</option>
              <option value="software">소프트웨어전공</option>
            </select>
          </label>
          <label>
            예시 상태
            <select
              value={scenario}
              onChange={(event) => setScenario(event.target.value as MockScenario)}
            >
              <option value="unmet">미충족 예시</option>
              <option value="met">충족 예시</option>
              <option value="review">미매칭 과목 확인 예시</option>
              <option value="program-difference">일반 충족 · 공학 미충족</option>
              <option value="thesis-unmet">학점 충족 · 논문 미충족</option>
            </select>
          </label>
        </div>
      </div>
      <p className={styles.hint} aria-live="polite">
        {program === 'engineering'
          ? '공학 선택자는 공학·일반 프로그램 요건과 공통 요건을 모두 충족해야 합니다.'
          : program === 'general'
            ? '일반 선택자는 일반 프로그램 요건과 공통 요건을 충족해야 합니다.'
            : '프로그램과 세부전공을 선택하면 가상 결과를 볼 수 있습니다.'}{' '}
        예시 설정 변경은 검수 입력값을 바꾸지 않습니다.
      </p>
      {result ? (
        <ResultsView result={result} onEdit={editCourses} />
      ) : (
        <p className={styles.reviewNote} role="status">
          프로그램 또는 세부전공이 선택되지 않았거나 입력값을 인식할 수 없습니다. 위에서 두 항목을
          모두 선택해 주세요.
        </p>
      )}
      <div className={styles.actions}>
        <div>
          <h2>이수내역이 다르게 보이나요?</h2>
          <p>검수 화면으로 돌아가 입력을 수정할 수 있어요. 실제 재판정은 API 연결 후 제공됩니다.</p>
        </div>
        <Button onClick={editCourses}>이수내역 수정</Button>
      </div>
      <p className={styles.footnote}>
        이 화면은 결과 UI(#25)의 mock 구현입니다. 실제 API 연동과 수강계획 시뮬레이션은 아직
        제공하지 않습니다.
      </p>
    </div>
  );
}
