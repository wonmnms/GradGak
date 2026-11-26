import { useState } from 'react';
import type { FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import Button from '../../components/Button/Button';
import { useDraft } from '../../context/useDraft';
import { parseProgram } from '../../context/program';
import type { Course } from '../../context/transcript';
import styles from './ReviewPage.module.css';

type CourseForm = {
  year: string;
  term: Course['term'];
  course_code: string;
  name: string;
  category: string;
  credits: string;
  grade: string;
  is_retake: boolean;
};

function toForm(course?: Course): CourseForm {
  return {
    year: String(course?.year ?? 2024),
    term: course?.term ?? '1',
    course_code: course?.course_code ?? '',
    name: course?.name ?? '',
    category: course?.category ?? '',
    credits: String(course?.credits ?? 3),
    grade: course?.grade ?? '',
    is_retake: course?.is_retake ?? false,
  };
}

function validate(form: CourseForm): string | null {
  const year = Number(form.year);
  const credits = Number(form.credits);
  if (!Number.isInteger(year) || year < 1900 || year > 2199) return '수강 연도를 1900~2199 사이의 정수로 입력해 주세요.';
  if (!form.name.trim()) return '과목명을 입력해 주세요.';
  if (!form.category.trim()) return '이수구분을 입력해 주세요.';
  if (!form.credits.trim() || !Number.isFinite(credits) || credits < 0) return '학점은 0 이상의 숫자로 입력해 주세요.';
  return null;
}

export default function ReviewPage() {
  const navigate = useNavigate();
  const { transcript, setTranscript, draft, setDraftField } = useDraft();
  const [editIndex, setEditIndex] = useState<number | null>(null);
  const [form, setForm] = useState<CourseForm>(toForm());
  const [formError, setFormError] = useState('');

  if (!transcript) {
    return (
      <div className={styles.page}>
        <p className={styles.eyebrow}>STEP 02 / 이수과목 검수</p>
        <h1>이수내역 검수·수정</h1>
        <section className={styles.card}>
          <h2>업로드한 이수내역이 없습니다.</h2>
          <p className={styles.muted}>이수내역은 브라우저 메모리에만 보관되며 새로고침하면 초기화됩니다.</p>
          <Button onClick={() => navigate('/upload')}>PDF 업로드하러 가기</Button>
        </section>
      </div>
    );
  }

  const courses = transcript.courses;
  const updateForm = <K extends keyof CourseForm>(key: K, value: CourseForm[K]) => setForm((before) => ({ ...before, [key]: value }));

  function saveCourse(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const error = validate(form);

    if (!transcript) return;
    
    if (error) { setFormError(error); return; }
    const next: Course = {
      year: Number(form.year), term: form.term,
      course_code: form.course_code.trim() || null,
      name: form.name.trim(), category: form.category.trim(), credits: Number(form.credits),
      grade: form.grade.trim() || null, is_retake: form.is_retake,
    };
    const list = [...courses];
    if (editIndex === -1) list.push(next);
    else if (editIndex !== null) list[editIndex] = next;
    setTranscript({ ...transcript, courses: list });
    setEditIndex(null);
    setFormError('');
  }

  const openEditor = (index: number) => { setEditIndex(index); setForm(toForm(index === -1 ? undefined : courses[index])); setFormError(''); };
  const totalCredits = courses.reduce((sum, c) => sum + c.credits, 0);
  const hasProgram = parseProgram(draft.program) !== null;
  const ready = courses.length > 0 && hasProgram && ['software', 'ai'].includes(draft.subMajor) && ['true', 'false'].includes(draft.thesis) && ['true', 'false'].includes(draft.topcit);

  return (
    <div className={styles.page}>
      <p className={styles.eyebrow}>STEP 02 / 이수과목 검수</p>
      <h1>이수내역 검수·수정</h1>
      <p className={styles.muted}>PDF에서 추출된 이수과목을 확인해 주세요. 잘못 인식된 과목은 수정하거나 직접 추가할 수 있습니다.</p>
      {transcript.parse_warnings.length > 0 && (
        <section className={styles.warnings} aria-label="파싱 경고" role="status">
          <strong>확인이 필요한 항목 {transcript.parse_warnings.length}개</strong>
          <ul>{transcript.parse_warnings.map((w, i) => <li key={`${w.row}-${i}`}>PDF 표 {w.row}행: {w.message}</li>)}</ul>
          <p>파싱 경고의 행 번호는 PDF 원본 표 기준이며, 아래 목록의 행 번호와 같지 않을 수 있습니다.</p>
        </section>
      )}
      <section className={styles.card} aria-labelledby="course-heading">
        <div className={styles.header}>
          <div><h2 id="course-heading">이수과목 목록</h2><p className={styles.muted}>{courses.length}과목 · 합계 {totalCredits}학점 (취득 인정 학점이 아닌 단순 합계)</p></div>
          <Button onClick={() => openEditor(-1)}>+ 과목 추가</Button>
        </div>
        {courses.length === 0 ? <p className={styles.muted}>추출된 과목이 없습니다. PDF가 올바른지 확인하고 필요한 과목을 직접 추가해 주세요.</p> : (
          <div className={styles.tableScroll}>
            <table className={styles.table}>
              <thead><tr><th scope="col">연도·학기</th><th scope="col">과목명</th><th scope="col">이수구분</th><th scope="col">학점</th><th scope="col">성적</th><th scope="col">관리</th></tr></thead>
              <tbody>{courses.map((c, i) => (
                <tr key={`${c.year}-${c.term}-${c.course_code ?? c.name}-${i}`}>
                  <td>{c.year} · {c.term === '1' ? '1학기' : c.term === '2' ? '2학기' : c.term === 'summer' ? '여름' : '겨울'}</td>
                  <td><strong>{c.name}</strong>{c.is_retake && <span className={styles.retake}> 재수강</span>}{c.course_code && <small>{c.course_code}</small>}</td>
                  <td>{c.category}</td><td>{c.credits}</td><td>{c.grade ?? '미확정'}</td>
                  <td className={styles.rowActions}><button type="button" onClick={() => openEditor(i)}>수정</button><button type="button" onClick={() => { if (window.confirm(`'${c.name}' 과목을 삭제할까요?`)) { setTranscript({ ...transcript, courses: courses.filter((_, idx) => idx !== i) }); setEditIndex(null); } }}>삭제</button></td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        )}
      </section>
      {editIndex !== null && (
        <section className={styles.card} aria-label="과목 편집">
          <h2>{editIndex === -1 ? '과목 추가' : '과목 수정'}</h2>
          <form onSubmit={saveCourse} className={styles.editor}>
            <label>수강 연도<input type="number" min="1900" max="2199" value={form.year} onChange={e => updateForm('year', e.target.value)} required /></label>
            <label>학기<select value={form.term} onChange={e => updateForm('term', e.target.value as Course['term'])}><option value="1">1학기</option><option value="2">2학기</option><option value="summer">여름학기</option><option value="winter">겨울학기</option></select></label>
            <label>학수번호 (선택)<input value={form.course_code} onChange={e => updateForm('course_code', e.target.value)} /></label>
            <label>과목명<input value={form.name} onChange={e => updateForm('name', e.target.value)} required /></label>
            <label>이수구분 (PDF 표기)<input value={form.category} onChange={e => updateForm('category', e.target.value)} placeholder="예: 전필, 전선" required /></label>
            <label>학점<input type="number" min="0" step="any" value={form.credits} onChange={e => updateForm('credits', e.target.value)} required /></label>
            <label>성적 (선택)<input value={form.grade} onChange={e => updateForm('grade', e.target.value)} placeholder="예: A0, P, F" /></label>
            <label className={styles.checkbox}><input type="checkbox" checked={form.is_retake} onChange={e => updateForm('is_retake', e.target.checked)} /> 재수강 과목</label>
            {formError && <p className={styles.fieldError} role="alert">{formError}</p>}
            <div className={styles.editorButtons}><Button type="submit">저장</Button><Button variant="secondary" onClick={() => setEditIndex(null)}>취소</Button></div>
          </form>
        </section>
      )}
      <section className={styles.card} aria-labelledby="requirement-heading">
        <h2 id="requirement-heading">졸업요건 확인 정보</h2>
        <p className={styles.muted}>KLAS PDF에 포함되지 않는 정보를 직접 선택해 주세요.</p>
        <div className={styles.editor}>
          <label>프로그램<select value={draft.program} onChange={e => setDraftField('program', e.target.value)}><option value="">선택하세요</option><option value="공학">공학</option><option value="일반">일반</option></select></label>
          <label>세부전공<select value={draft.subMajor} onChange={e => setDraftField('subMajor', e.target.value)}><option value="">선택하세요</option><option value="software">소프트웨어전공</option><option value="ai">인공지능전공</option></select></label>
          <label>졸업논문(작품) '가' 판정<select value={draft.thesis} onChange={e => setDraftField('thesis', e.target.value)}><option value="">선택하세요</option><option value="true">받음</option><option value="false">받지 않음</option></select></label>
          <label>TOPCIT 응시 여부<select value={draft.topcit} onChange={e => setDraftField('topcit', e.target.value)}><option value="">선택하세요</option><option value="true">응시함</option><option value="false">응시하지 않음</option></select></label>
        </div>
      </section>
      <div className={styles.footer}>
        <Button variant="secondary" onClick={() => navigate('/upload')}>← 다시 업로드</Button>
        <div className={styles.next}>
          <p className={styles.muted}>{ready ? '입력값이 준비되었습니다. 실제 판정 API 연동은 후속 통합 작업에서 진행됩니다.' : '과목 목록과 졸업요건 정보를 모두 입력해 주세요.'}</p>
          <Button disabled title="실제 졸업요건 판정 API 연결 후 활성화됩니다.">졸업요건 판정하기 →</Button>
        </div>
      </div>
    </div>
  );
}
