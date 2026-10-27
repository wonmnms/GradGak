import { Navigate, Route, Routes } from 'react-router-dom';
import Layout from './components/Layout/Layout';
import UploadPage from './pages/UploadPage/UploadPage';
import ReviewPage from './pages/ReviewPage/ReviewPage';
import ResultsPage from './pages/ResultsPage/ResultsPage';
import NotFoundPage from './pages/NotFoundPage/NotFoundPage';

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Navigate to="/upload" replace />} />
        <Route path="upload" element={<UploadPage />} />
        <Route path="review" element={<ReviewPage />} />
        <Route path="results" element={<ResultsPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}
