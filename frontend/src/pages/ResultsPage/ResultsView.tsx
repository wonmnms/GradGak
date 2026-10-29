import Button from '../../components/Button/Button';
import { creditProgress, getResultSummary, hasCourseCount } from './results.presentation';
import type {
  CommonRequirement,
  EvaluationResult,
  Program,
  ProgramResult,
  ResultStatus,
} from './result.types';
import styles from './ResultsPage.module.css';

const statusLabels: Record<ResultStatus, string> = { met: '충족', unmet: '미충족' };
const programTitles: Record<Program, string> = {
  engineering: '공학 프로그램',
  general: '일반 프로그램',
};
function StatusBadge({ status }: { status: ResultStatus }) {
  return <span className={styles.badge + ' ' + styles[status]}>{statusLabels[status]}</span>;
}
function RequirementList({ items }: { items: CommonRequirement[] }) {
  return (
    <ul className={styles.requirements}>
      {items.map((item) => (
        <li key={item.id}>
          <div className={styles.requirementRow}>
            <strong>{item.label}</strong>
            <span className={styles.requirementValue}>
              {hasCourseCount(item) && (
                <span className={styles.detail}>
                  이수 {item.completed_count}과목 / 필요 {item.required_count}과목 이상
                </span>
              )}
              <StatusBadge status={item.status} />
            </span>
          </div>
          {hasCourseCount(item) && (
            <details className={styles.courseDetails}>
              <summary>
                지정 과목 {item.courses.length}개 중 {item.required_count}개 이상 이수 · 과목 보기
              </summary>
              <p className={styles.hint}>아래 과목을 전부 이수해야 한다는 뜻이 아닙니다.</p>
              <ul>
                {item.courses.map((course, index) => (
                  <li key={(course.course_code ?? course.name) + '-' + index}>
                    <span>{course.name}</span>
                    <span className={course.completed ? styles.met : styles.detail}>
                      {course.completed ? '이수' : '미이수'}
                    </span>
                  </li>
                ))}
              </ul>
            </details>
          )}
        </li>
      ))}
    </ul>
  );
}
function ProgramCard({ result }: { result: ProgramResult }) {
  const title = programTitles[result.program];
  const { total } = result;
  const percent = creditProgress(total);
  return (
    <section className={styles.card} aria-labelledby={result.program + '-title'}>
      <div className={styles.cardHeader}>
        <h2 id={result.program + '-title'}>{title}</h2>
        <span className={styles.requirementValue}>
          <span className={styles.detail}>프로그램 요건</span>
          <StatusBadge status={result.status} />
        </span>
      </div>
      <p className={styles.total}>
        <strong>{total.earned}</strong>
        <span> / {total.required}학점</span>
      </p>
      <div
        className={styles.progress}
        role="progressbar"
        aria-label={title + ' 총학점 이수율'}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={percent}
      >
        <span style={{ width: percent + '%' }} />
      </div>
      <div className={styles.progressLabels}>
        <span>총학점 기준 {percent}% 이수</span>
        <span>
          {total.remaining > 0 ? total.remaining + '학점 부족' : '부족 학점 없음'} · 총학점{' '}
          {statusLabels[total.status]}
        </span>
      </div>
      <table className={styles.creditTable}>
        <caption>{title} 요건별 학점 현황 · 단위: 학점</caption>
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
      {result.course_groups.length > 0 && (
        <>
          <h3 className={styles.subheading}>프로그램별 선택 과목 요건</h3>
          <RequirementList items={result.course_groups} />
        </>
      )}
    </section>
  );
}
export default function ResultsView({
  result,
  onEdit,
}: {
  result: EvaluationResult;
  onEdit: () => void;
}) {
  const summary = getResultSummary(result);
  return (
    <>
      <section className={styles.summaryCard} aria-labelledby="graduation-title" aria-live="polite">
        <p className={styles.eyebrow}>최종 졸업 판정 · 가상 응답</p>
        <h2 id="graduation-title" className={styles[summary.status]}>
          {summary.label}
        </h2>
        {summary.needsReview ? (
          <p>
            현재 응답 판정은 {statusLabels[result.graduation_status]}이지만, 판정에서 제외된 과목이
            있습니다. 실제 졸업 가능 여부를 확정하는 안내가 아닙니다.
          </p>
        ) : (
          <p>
            {result.graduation_status === 'met'
              ? '이 가상 응답은 공통 요건과 해당 프로그램 요건을 모두 충족합니다.'
              : '공통 요건 또는 프로그램 요건 중 아직 충족하지 못한 항목이 있습니다.'}
          </p>
        )}
      </section>
      {result.unmatched_courses.length > 0 && (
        <section className={styles.warningPanel} aria-labelledby="unmatched-title">
          <h2 id="unmatched-title">확인이 필요한 과목 {result.unmatched_courses.length}개</h2>
          <p>
            과목 데이터와 매칭되지 않아 판정에서 빠진 과목입니다. 검수 화면에서 과목명과 학수번호를
            확인해 주세요.
          </p>
          <ul>
            {result.unmatched_courses.map((course) => (
              <li key={course.index}>
                <strong>{course.name}</strong>
                <p>
                  검수 목록 {course.index + 1}번째 과목 · {course.reason}
                </p>
              </li>
            ))}
          </ul>
          <Button variant="secondary" onClick={onEdit}>
            검수 화면에서 확인
          </Button>
        </section>
      )}
      <section className={styles.commonCard} aria-labelledby="common-title">
        <h2 id="common-title">공통 요건</h2>
        <p className={styles.hint}>
          프로그램과 관계없이 한 번만 확인하는 요건입니다. 필요한 개수만 이수하는 선택 과목 요건은
          개별 필수과목과 구분합니다.
        </p>
        {result.common_requirements.length > 0 ? (
          <RequirementList items={result.common_requirements} />
        ) : (
          <p className={styles.empty}>응답에 공통 요건이 없습니다.</p>
        )}
      </section>
      <div className={styles.grid}>
        {result.program_results.map((program) => (
          <ProgramCard key={program.program} result={program} />
        ))}
      </div>
      <section className={styles.missing} aria-labelledby="missing-title">
        <h2 id="missing-title">미이수 필수과목</h2>
        <p className={styles.hint}>
          지정 과목 중 일부를 선택하는 요건과 달리, 각각 이수해야 하는 필수과목 목록입니다.
        </p>
        <div className={styles.missingGrid}>
          {result.program_results.map((program) => (
            <section key={program.program} aria-labelledby={program.program + '-missing'}>
              <h3 id={program.program + '-missing'}>{programTitles[program.program]}</h3>
              {program.missing_required_courses.length === 0 ? (
                <p className={styles.empty}>이 예시에는 미이수 필수과목이 없습니다.</p>
              ) : (
                <ul className={styles.courseList}>
                  {program.missing_required_courses.map((course, index) => (
                    <li key={(course.course_code ?? course.name) + '-' + index}>
                      <div>
                        <strong>{course.name}</strong>
                        <p>
                          {course.category}
                          {course.course_code ? ' · ' + course.course_code : ''}
                        </p>
                      </div>
                      <span>{course.credits}학점</span>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          ))}
        </div>
      </section>
    </>
  );
}
