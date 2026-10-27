import { useNavigate } from 'react-router-dom';
import Button from '../../components/Button/Button';
import DraftFields from '../../components/Field/DraftFields';
import Notice from '../../components/Notice/Notice';
import styles from '../Page.module.css';

export default function ReviewPage() {
  const navigate = useNavigate();
  return (
    <div>
      <h1>이수내역 검수·수정</h1>
      <Notice>
        임시 화면입니다. 파싱 결과 표시와 수정 기능은 API 확정 후 구현됩니다. 업로드 화면에서 입력한
        값이 그대로 유지되는지만 확인할 수 있습니다.
      </Notice>
      <section className={styles.section} aria-labelledby="review-draft">
        <h2 id="review-draft">임시 입력 값</h2>
        <DraftFields />
      </section>
      <div className={styles.actions}>
        <Button variant="secondary" onClick={() => navigate('/upload')}>
          업로드로 돌아가기
        </Button>
        <Button onClick={() => navigate('/results')}>결과 화면으로 이동</Button>
      </div>
    </div>
  );
}
