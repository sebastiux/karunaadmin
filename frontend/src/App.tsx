import { Navigate, Route, Routes, Link, useLocation, NavLink } from "react-router-dom";
import { useAuth } from "./auth";
import { ROLE_LABELS, isAnyAdmin, isCommercialTeam, isDevTeam } from "./types";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import ProjectView from "./pages/ProjectView";
import TicketMonitor from "./pages/TicketMonitor";
import Commercial from "./pages/Commercial";
import Users from "./pages/Users";

function Shell({ children }: { children: React.ReactNode }) {
  const { user, logout } = useAuth();
  const loc = useLocation();
  const role = user?.role;
  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="topbar-left">
          <Link to="/" className="brand">
            <span className="brand-mark">◆</span> Karuna
            <span className="brand-thin">Admin</span>
          </Link>
          <nav className="mainnav">
            {isDevTeam(role) && <NavLink to="/" end>Projects</NavLink>}
            {isDevTeam(role) && <NavLink to="/tickets">Ticket Monitor</NavLink>}
            {isCommercialTeam(role) && <NavLink to="/commercial">Commercial</NavLink>}
            {isAnyAdmin(role) && <NavLink to="/users">Team</NavLink>}
            {!isDevTeam(role) && !isCommercialTeam(role) && (
              <NavLink to="/" end>Projects</NavLink>
            )}
          </nav>
        </div>
        <div className="topbar-right">
          {user && (
            <>
              <span className="user-chip">
                {user.name}
                <span className="role-badge">{ROLE_LABELS[user.role] ?? user.role}</span>
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
        <Route path="/tickets" element={<TicketMonitor />} />
        <Route path="/commercial" element={<Commercial />} />
        <Route path="/users" element={<Users />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Shell>
  );
}
