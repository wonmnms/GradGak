import Button from '../../components/Button/Button';
import {
  creditProgress,
  formatCredit,
  getResultSummary,
  hasCourseCount,
  remainingLabel,
  statusLabels,
} from './results.presentation';
import type {
  CommonRequirement,
  CourseNotice,
  EvaluationResult,
  Program,
  ProgramResult,
  ResultStatus,
} from './result.types';
import styles from './ResultsPage.module.css';

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
        <strong>{formatCredit(total.earned)}</strong>
        <span> / {formatCredit(total.required)}학점</span>
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
          {remainingLabel(total)} · 총학점 {statusLabels[total.status]}
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
              <th scope="row">
                {item.label}
                {item.status === 'pending' && item.reason && (
                  <span className={styles.reason}>{item.reason}</span>
                )}
              </th>
              <td>{formatCredit(item.required)}</td>
              <td>{formatCredit(item.earned)}</td>
              <td className={styles.remaining}>{formatCredit(item.remaining)}</td>
              <td>
                <span className={styles[item.status]}>{statusLabels[item.status]}</span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {result.categories.some((item) => item.status === 'pending') && (
        <p className={styles.hint}>— 표시는 규칙 데이터가 없어 아직 계산하지 않은 값입니다.</p>
      )}
      {result.course_groups.length > 0 && (
        <>
          <h3 className={styles.subheading}>프로그램별 선택 과목 요건</h3>
          <RequirementList items={result.course_groups} />
        </>
      )}
    </section>
  );
}
function NoticeList({ items }: { items: CourseNotice[] }) {
  return (
    <ul>
      {items.map((course) => (
        <li key={course.index + '-' + course.reason}>
          <strong>{course.name}</strong>
          <p>
            검수 목록 {course.index + 1}번째 과목 · {course.reason}
          </p>
        </li>
      ))}
    </ul>
  );
}
const summaryDescriptions: Record<ResultStatus, string> = {
  met: '이 가상 응답은 공통 요건과 해당 프로그램 요건을 모두 충족합니다.',
  unmet: '공통 요건 또는 프로그램 요건 중 아직 충족하지 못한 항목이 있습니다.',
  pending:
    '일부 요건의 규칙 데이터가 아직 없어 최종 충족 여부를 판정하지 않았습니다. 미충족 항목이 없더라도 졸업 가능으로 보지 마세요.',
};
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
            서버 판정은 '{statusLabels[result.graduation_status]}'이지만, 과목 데이터와 매칭되지
            않아 판정에서 빠진 과목이 있습니다. 실제 졸업 가능 여부를 확정하는 안내가 아닙니다.
          </p>
        ) : (
          <p>{summaryDescriptions[result.graduation_status]}</p>
        )}
      </section>
      {result.warnings.length > 0 && (
        <section className={styles.warningPanel} aria-labelledby="warnings-title">
          <h2 id="warnings-title">판정 안내 {result.warnings.length}건</h2>
          <ul>
            {result.warnings.map((warning, index) => (
              <li key={index + '-' + warning}>{warning}</li>
            ))}
          </ul>
        </section>
      )}
      {result.unmatched_courses.length > 0 && (
        <section className={styles.warningPanel} aria-labelledby="unmatched-title">
          <h2 id="unmatched-title">확인이 필요한 과목 {result.unmatched_courses.length}개</h2>
          <p>
            과목 데이터와 매칭되지 않아 판정에서 빠진 과목입니다. 검수 화면에서 과목명과 학수번호를
            확인해 주세요.
          </p>
          <NoticeList items={result.unmatched_courses} />
          <Button variant="secondary" onClick={onEdit}>
            검수 화면에서 확인
          </Button>
        </section>
      )}
      {result.excluded_courses.length > 0 && (
        <section className={styles.commonCard} aria-labelledby="excluded-title">
          <h2 id="excluded-title">판정에서 제외한 과목 {result.excluded_courses.length}개</h2>
          <p className={styles.hint}>
            F·NP·빈 성적·(삭제)·재수강 중복·중복 입력 때문에 학점과 이수에서 빠진 과목입니다. 잘못
            빠졌다면 검수 화면에서 성적과 재수강 표시를 확인해 주세요.
          </p>
          <div className={styles.noticeList}>
            <NoticeList items={result.excluded_courses} />
          </div>
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
                program.status === 'pending' ? (
                  <p className={styles.emptyPending}>
                    응답에 미이수 필수과목이 없습니다. 판정 보류 상태라 확정된 결과는 아닙니다.
                  </p>
                ) : (
                  <p className={styles.empty}>이 예시에는 미이수 필수과목이 없습니다.</p>
                )
              ) : (
                <ul className={styles.courseList}>
                  {program.missing_required_courses.map((course, index) => (
                    <li key={(course.course_code ?? course.name) + '-' + index}>
                      <div>
                        <strong>{course.name}</strong>
                        {(course.category || course.course_code) && (
                          <p>{[course.category, course.course_code].filter(Boolean).join(' · ')}</p>
                        )}
                      </div>
                      {course.credits !== null && <span>{course.credits}학점</span>}
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
