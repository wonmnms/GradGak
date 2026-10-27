import { useNavigate } from 'react-router-dom';
import Button from '../../components/Button/Button';
import DraftFields from '../../components/Field/DraftFields';
import Notice from '../../components/Notice/Notice';
import styles from '../Page.module.css';

export default function UploadPage() {
  const navigate = useNavigate();
  return (
    <div>
      <h1>이수내역 업로드</h1>
      <Notice>
        임시 화면입니다. 실제 파일 업로드와 파싱은 아직 연결되지 않았습니다. 아래 입력값은
        메모리에만 보관되며 새로고침하면 사라집니다.
      </Notice>
      <section className={styles.section} aria-labelledby="upload-draft">
        <h2 id="upload-draft">임시 입력(화면 이동 시 유지 확인용)</h2>
        <DraftFields />
      </section>
      <div className={styles.actions}>
        <Button onClick={() => navigate('/review')}>검수·수정 화면으로 이동</Button>
      </div>
    </div>
  );
}
