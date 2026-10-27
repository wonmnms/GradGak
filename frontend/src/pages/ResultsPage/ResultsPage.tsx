import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Button from '../../components/Button/Button';
import { useDraft } from '../../context/useDraft';
import { parseProgram } from '../../context/program';
import { getMockResults } from './results.mock';
import type { MockScenario, Program, ProgramResult, ResultStatus } from './result.types';
import styles from './ResultsPage.module.css';

const statusLabels: Record<ResultStatus, string> = {
  met: '충족',
  unmet: '미충족',
  review: '확인 필요',
};
const scenarioTitles: Record<MockScenario, string> = {
  unmet: '졸업까지 무엇이 남았을까요?',
  met: '모든 예시 요건을 충족했어요',
  review: '확인이 필요한 요건이 있어요',
  'program-difference': '프로그램별 예시 판정이 달라요',
  'thesis-unmet': '학점 외에 남은 요건이 있어요',
};
function StatusBadge({ status }: { status: ResultStatus }) {
  return <span className={styles.badge + ' ' + styles[status]}>{statusLabels[status]}</span>;
}
function ProgramCard({ result }: { result: ProgramResult }) {
  const { total } = result;
  const percent =
    total.required > 0
      ? Math.min(100, Math.max(0, Math.round((total.earned / total.required) * 100)))
      : 0;
  return (
    <section className={styles.card} aria-labelledby={result.program + '-title'}>
      <div className={styles.cardHeader}>
        <h2 id={result.program + '-title'}>{result.title}</h2>
        <StatusBadge status={result.status} />
      </div>
      <p className={styles.total}>
        <strong>{total.earned}</strong>
        <span> / {total.required}학점</span>
      </p>
      <div
        className={styles.progress}
        role="progressbar"
        aria-label={result.title + ' 총학점 이수율'}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={percent}
      >
        <span style={{ width: percent + '%' }} />
      </div>
      <div className={styles.progressLabels}>
        <span>총학점 기준 {percent}% 이수</span>
        <span>{total.remaining > 0 ? total.remaining + '학점 부족' : '부족 학점 없음'}</span>
      </div>
      {total.status === 'review' && (
        <p className={styles.reviewNote}>예시 학점은 잠정 값입니다. 확인 후 판정해야 합니다.</p>
      )}
      <table className={styles.creditTable}>
        <caption>{result.title} 요건별 학점 현황 · 단위: 학점</caption>
        <thead>
          <tr>
            <th scope="col">구분</th>
            <th scope="col">요구</th>
            <th scope="col">이수</th>
            <th scope="col">부족</th>
            <th scope="col">상태</th>
          </tr>
        </thead>
        <tbody>
          {result.categories.map((item) => (
            <tr key={item.id}>
              <th scope="row">{item.label}</th>
              <td>{item.required}</td>
              <td>{item.earned}</td>
              <td className={styles.remaining}>{item.remaining}</td>
              <td>
                <span className={styles[item.status]}>{statusLabels[item.status]}</span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <h3 className={styles.subheading}>학점 외 요건</h3>
      <ul className={styles.requirements}>
        {result.specialRequirements.map((item) => (
          <li key={item.id}>
            <span>{item.label}</span>
            <span className={styles.requirementValue}>
              {item.detail && <span className={styles.detail}>{item.detail}</span>}
              <span className={styles[item.status]}>{statusLabels[item.status]}</span>
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}
export default function ResultsPage() {
  const navigate = useNavigate();
  const { draft } = useDraft();
  const [program, setProgram] = useState<Program | ''>(() => parseProgram(draft.program) ?? '');
  const [scenario, setScenario] = useState<MockScenario>('unmet');
  const results = getMockResults(scenario).filter(
    (result) =>
      program === 'engineering' || (program === 'general' && result.program === 'general'),
  );
  return (
    <div className={styles.page}>
      <div className={styles.intro}>
        <p className={styles.eyebrow}>졸업요건 판정 결과 · 화면 개발용</p>
        <h1>{scenarioTitles[scenario]}</h1>
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
        <h2>프로그램별 판정</h2>
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
            예시 상태
            <select
              value={scenario}
              onChange={(event) => setScenario(event.target.value as MockScenario)}
            >
              <option value="unmet">미충족 예시</option>
              <option value="met">충족 예시</option>
              <option value="review">확인 필요 예시</option>
              <option value="program-difference">일반 충족 · 공학 미충족</option>
              <option value="thesis-unmet">학점 충족 · 논문 미충족</option>
            </select>
          </label>
        </div>
      </div>
      <p className={styles.hint} aria-live="polite">
        {program === ''
          ? '프로그램을 선택하면 가상 데이터 결과를 확인할 수 있습니다.'
          : program === 'engineering'
            ? '공학 선택자는 공학·일반 결과를 함께 확인합니다.'
            : '일반 선택자는 일반 프로그램 결과만 확인합니다.'}{' '}
        프로그램 보기와 예시 상태 변경은 검수 입력값을 바꾸지 않습니다.
      </p>
      {program ? (
        <>
          <div className={styles.grid}>
            {results.map((result) => (
              <ProgramCard key={result.program} result={result} />
            ))}
          </div>
          <section className={styles.missing} aria-labelledby="missing-title">
            <h2 id="missing-title">미이수 필수과목</h2>
            <p className={styles.hint}>부족한 학점과 별개로 반드시 이수해야 하는 과목입니다.</p>
            <div className={styles.missingGrid}>
              {results.map((result) => (
                <section key={result.program} aria-labelledby={result.program + '-missing'}>
                  <h3 id={result.program + '-missing'}>{result.title}</h3>
                  {result.missingCourses.length === 0 ? (
                    <p className={styles.empty}>이 예시에는 미이수 필수과목이 없습니다.</p>
                  ) : (
                    <ul className={styles.courseList}>
                      {result.missingCourses.map((course) => (
                        <li key={course.id}>
                          <div>
                            <strong>{course.name}</strong>
                            <p>{course.category}</p>
                          </div>
                          <span>{course.credit}학점</span>
                        </li>
                      ))}
                    </ul>
                  )}
                </section>
              ))}
            </div>
            <p className={styles.footnote}>
              ‘N개 중 선택’ 형태의 세부전공 요건은 위 학점 외 요건에 표시하며, 여기의 필수과목
              목록과 구분합니다.
            </p>
          </section>
        </>
      ) : (
        <p className={styles.reviewNote} role="status">
          {draft.program.trim() && !parseProgram(draft.program)
            ? '입력된 프로그램을 확인할 수 없습니다. 프로그램 보기에서 공학 또는 일반을 선택해 주세요.'
            : '프로그램이 선택되지 않았습니다. 프로그램 보기에서 공학 또는 일반을 선택해 주세요.'}
        </p>
      )}
      <div className={styles.actions}>
        <div>
          <h2>이수내역이 다르게 보이나요?</h2>
          <p>검수 화면으로 돌아가 입력을 수정할 수 있어요. 실제 재판정은 API 연결 후 제공됩니다.</p>
        </div>
        <Button onClick={() => navigate('/review')}>이수내역 수정</Button>
      </div>
      <p className={styles.footnote}>
        이 화면은 결과 UI(#25)의 mock 구현입니다. 실제 API 연동과 수강계획 시뮬레이션은 아직
        제공하지 않습니다.
      </p>
    </div>
  );
}
