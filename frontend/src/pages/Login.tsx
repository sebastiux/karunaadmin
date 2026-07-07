import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth";

export default function Login() {
  const { login } = useAuth();
  const nav = useNavigate();
  const [email, setEmail] = useState("admin@karuna.app");
  const [password, setPassword] = useState("admin123");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      await login(email, password);
      nav("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="center-screen login-bg">
      <form className="login-card" onSubmit={submit}>
        <div className="login-brand">
          <span className="brand-mark">◆</span> Karuna
          <span className="brand-thin">Admin</span>
        </div>
        <p className="login-sub">Project administration platform</p>

        <label>Email</label>
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          autoFocus
        />

        <label>Password</label>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />

        {error && <div className="alert error">{error}</div>}

        <button className="btn primary full" disabled={busy}>
          {busy ? "Signing in…" : "Sign in"}
        </button>
        <p className="login-hint">
          Default admin: <code>admin@karuna.app</code> / <code>admin123</code>
        </p>
      </form>
    </div>
  );
}
