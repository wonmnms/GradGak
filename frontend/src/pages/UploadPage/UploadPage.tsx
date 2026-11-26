import { useRef, useState } from 'react';
import type { ChangeEvent, FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import Button from '../../components/Button/Button';
import { useDraft } from '../../context/useDraft';
import type { TranscriptParseResponse } from '../../context/transcript';
import styles from './UploadPage.module.css';

const MAX_BYTES = 10 * 1024 * 1024;
const API_BASE = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000').replace(/\/$/, '');

function errorMessage(status: number, data: unknown): string {
  if (data && typeof data === 'object' && 'detail' in data) {
    const detail = (data as { detail: unknown }).detail;
    if (detail && typeof detail === 'object' && 'message' in detail) {
      const message = (detail as { message: unknown }).message;
      if (typeof message === 'string') return message;
    }
  }
  if (status === 413) return '파일이 너무 큽니다. 10 MiB 이하의 PDF를 선택해 주세요.';
  if (status === 422) return 'KLAS 이수내역 PDF 파일 하나를 다시 선택해 주세요.';
  return 'PDF를 읽지 못했습니다. KLAS에서 이수내역 원본 PDF를 다시 내려받아 시도해 주세요.';
}

export default function UploadPage() {
  const navigate = useNavigate();
  const { setTranscript } = useDraft();
  const fileRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  function onFileChange(event: ChangeEvent<HTMLInputElement>) {
    const selected = event.target.files?.[0] ?? null;
    setError('');
    setFile(null);
    if (!selected) return;
    if (!selected.name.toLowerCase().endsWith('.pdf') || (selected.type && selected.type !== 'application/pdf')) {
      setError('PDF 형식의 KLAS 이수내역 파일만 선택할 수 있습니다.');
      event.target.value = '';
      return;
    }
    if (selected.size === 0 || selected.size > MAX_BYTES) {
      setError('파일 크기는 0바이트보다 크고 10 MiB 이하여야 합니다.');
      event.target.value = '';
      return;
    }
    setFile(selected);
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!file || busy) return;
    setBusy(true);
    setError('');
    const data = new FormData();
    data.append('file', file);
    try {
      const response = await fetch(`${API_BASE}/transcripts/parse`, { method: 'POST', body: data });
      const body: unknown = await response.json().catch(() => null);
      if (!response.ok) {
        setError(errorMessage(response.status, body));
        return;
      }
      if (!body || typeof body !== 'object' || !('courses' in body) || !Array.isArray(body.courses)) {
        setError('서버의 응답 형식이 올바르지 않습니다. 관리자에게 문의해 주세요.');
        return;
      }
      const result = body as TranscriptParseResponse;
      setTranscript(result);
      navigate('/review');
    } catch {
      setError('서버에 연결할 수 없습니다. 백엔드가 실행 중인지 확인하고 다시 시도해 주세요.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className={styles.page}>
      <div className={styles.intro}>
        <p className={styles.eyebrow}>STEP 01 / 이수내역 등록</p>
        <h1>KLAS 이수내역 업로드</h1>
        <p className={styles.muted}>이수내역 PDF를 업로드하면 과목을 추출하고, 다음 단계에서 직접 확인할 수 있습니다.</p>
      </div>
      <form onSubmit={onSubmit}>
        <section className={styles.card} aria-labelledby="upload-title">
          <div className={styles.cardHeading}>
            <div>
              <h2 id="upload-title">이수내역 PDF 선택</h2>
              <p className={styles.muted}>KLAS에서 내려받은 원본 PDF 파일 1개를 준비해 주세요.</p>
            </div>
            <span className={styles.badge}>PDF · 최대 10 MiB</span>
          </div>
          <input ref={fileRef} className={styles.hiddenFile} id="transcript-file" type="file" accept=".pdf,application/pdf" onChange={onFileChange} disabled={busy} aria-describedby="file-help" />
          <label htmlFor="transcript-file" className={styles.dropzone}>
            <span className={styles.fileIcon} aria-hidden="true">↑</span>
            <strong>{file ? file.name : '클릭해서 PDF 파일 선택하기'}</strong>
            <span id="file-help">{file ? `${(file.size / 1024 / 1024).toFixed(2)} MiB · 선택됨` : '확장자 .pdf · 최대 10 MiB'}</span>
          </label>
          {file && <button className={styles.remove} type="button" disabled={busy} onClick={() => { setFile(null); if (fileRef.current) fileRef.current.value = ''; }}>선택 취소</button>}
          {error && <div className={styles.error} role="alert"><strong>업로드 실패</strong><p>{error}</p><p>KLAS의 이수내역 페이지에서 텍스트를 선택할 수 있는 원본 PDF를 내려받아 주세요. 화면 캡처나 이미지 PDF는 지원하지 않습니다.</p></div>}
        </section>
        <section className={styles.info} aria-labelledby="upload-info-title">
          <h2 id="upload-info-title">업로드 전 확인</h2>
          <ul>
            <li>이수내역 PDF만 지원합니다. 공학인증점검표는 지원 대상이 아닙니다.</li>
            <li>PDF와 추출된 이수과목은 서버에 영구 저장하지 않습니다.</li>
            <li>파싱 결과가 틀릴 수 있으므로 다음 단계에서 과목을 꼭 검수해 주세요.</li>
          </ul>
        </section>
        <div className={styles.actions}>
          <span className={styles.muted} aria-live="polite">{busy ? 'PDF를 분석하고 있습니다…' : file ? '파일이 준비되었습니다.' : 'PDF 파일을 먼저 선택해 주세요.'}</span>
          <Button type="submit" disabled={!file || busy}>{busy ? '분석 중…' : '이수내역 분석하기 →'}</Button>
        </div>
      </form>
    </div>
  );
}
