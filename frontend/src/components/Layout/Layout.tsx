import { Link, NavLink, Outlet } from 'react-router-dom';
import styles from './Layout.module.css';

const steps = [
  { to: '/upload', label: '1. 업로드' },
  { to: '/review', label: '2. 검수·수정' },
  { to: '/results', label: '3. 결과' },
];

export default function Layout() {
  return (
    <div className={styles.shell}>
      <header className={styles.header}>
        <div className={styles.inner}>
          <Link to="/upload" className={styles.logo} aria-label="졸업각 업로드 화면">
            졸업각 GradGak
          </Link>
          <nav aria-label="진행 단계">
            <ol className={styles.steps}>
              {steps.map((step) => (
                <li key={step.to}>
                  <NavLink
                    to={step.to}
                    className={({ isActive }) =>
                      [styles.step, isActive ? styles.active : ''].filter(Boolean).join(' ')
                    }
                  >
                    {step.label}
                  </NavLink>
                </li>
              ))}
            </ol>
          </nav>
        </div>
      </header>
      <main className={styles.main}>
        <Outlet />
      </main>
    </div>
  );
}
