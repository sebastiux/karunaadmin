import { Navigate, Route, Routes, Link, useLocation } from "react-router-dom";
import { useAuth } from "./auth";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import ProjectView from "./pages/ProjectView";

function Shell({ children }: { children: React.ReactNode }) {
  const { user, logout } = useAuth();
  const loc = useLocation();
  return (
    <div className="app-shell">
      <header className="topbar">
        <Link to="/" className="brand">
          <span className="brand-mark">◆</span> Karuna<span className="brand-thin">Admin</span>
        </Link>
        <div className="topbar-right">
          {user && (
            <>
              <span className="user-chip">
                {user.name}
                <span className={`role-badge role-${user.role}`}>{user.role}</span>
              </span>
              <button className="btn ghost" onClick={logout}>
                Sign out
              </button>
            </>
          )}
        </div>
      </header>
      <main key={loc.pathname}>{children}</main>
    </div>
  );
}

export default function App() {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="center-screen">
        <div className="spinner" />
      </div>
    );
  }

  if (!user) {
    return (
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    );
  }

  return (
    <Shell>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/projects/:id" element={<ProjectView />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Shell>
  );
}
