import { Link } from 'react-router-dom';

export default function NotFoundPage() {
  return (
    <div>
      <h1>페이지를 찾을 수 없습니다</h1>
      <p>주소를 다시 확인해 주세요.</p>
      <Link to="/upload">업로드 화면으로 이동</Link>
    </div>
  );
}
