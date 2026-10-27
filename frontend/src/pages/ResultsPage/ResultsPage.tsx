import { useNavigate } from 'react-router-dom';
import Button from '../../components/Button/Button';
import Notice from '../../components/Notice/Notice';
import styles from '../Page.module.css';

const sections = [
  '프로그램별 판정 요약',
  '요건별 학점 현황',
  '세부전공필수·졸업논문·TOPCIT',
  '미이수 필수과목',
];

export default function ResultsPage() {
  const navigate = useNavigate();
  return (
    <div>
      <h1>졸업요건 판정 결과</h1>
      <Notice>API 연결 전 공통 화면 틀입니다.</Notice>
      {sections.map((title, i) => (
        <section className={styles.section} key={title} aria-labelledby={`result-${i}`}>
          <h2 id={`result-${i}`}>{title}</h2>
          <p>결과 데이터가 연결되면 이곳에 표시됩니다.</p>
        </section>
      ))}
      <div className={styles.actions}>
        <Button variant="secondary" onClick={() => navigate('/review')}>
          이수내역 수정
        </Button>
      </div>
    </div>
  );
}
