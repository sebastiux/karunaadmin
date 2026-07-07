import { useEffect, useState } from "react";
import { api } from "../api";
import { useAuth } from "../auth";
import { ROLE_LABELS, isAnyAdmin } from "../types";
import type { Project, Role, User } from "../types";

// Mirrors backend _CREATABLE in routers/auth.py.
const CREATABLE: Record<string, Role[]> = {
  admin: ["admin", "admin_dev", "admin_comercial", "dev", "comercial", "client"],
  admin_dev: ["dev", "admin_dev", "client"],
  admin_comercial: ["comercial", "admin_comercial"],
};

export default function Users() {
  const { user } = useAuth();
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [show, setShow] = useState(false);

  const allowedRoles = CREATABLE[user?.role ?? ""] ?? [];
  const canCreate = isAnyAdmin(user?.role) && allowedRoles.length > 0;

  async function load() {
    setLoading(true);
    try {
      setUsers(await api.users());
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => { load(); }, []);

  if (loading) return <div className="container"><div className="spinner" /></div>;

  return (
    <div className="container">
      <div className="page-head">
        <div>
          <h1>Team</h1>
          <p className="muted">People with access to the platform and their roles.</p>
        </div>
        {canCreate && (
          <button className="btn primary" onClick={() => setShow(true)}>+ Add user</button>
        )}
      </div>

      <div className="user-table">
        <div className="user-row user-head">
          <span>Name</span><span>Email</span><span>Role</span><span>Joined</span>
        </div>
        {users.map((u) => (
          <div key={u.id} className="user-row">
            <span className="u-name">{u.name}</span>
            <span className="muted">{u.email}</span>
            <span><span className={`role-tag role-${u.role}`}>{ROLE_LABELS[u.role] ?? u.role}</span></span>
            <span className="muted">{new Date(u.created_at).toLocaleDateString()}</span>
          </div>
        ))}
      </div>

      {show && canCreate && (
        <CreateUser
          allowedRoles={allowedRoles}
          onClose={() => setShow(false)}
          onCreated={(u) => setUsers((xs) => [...xs, u])}
        />
      )}
    </div>
  );
}

function CreateUser({
  allowedRoles, onClose, onCreated,
}: {
  allowedRoles: Role[];
  onClose: () => void;
  onCreated: (u: User) => void;
}) {
  const [f, setF] = useState({
    name: "", email: "", password: "", role: allowedRoles[0],
  });
  const [projects, setProjects] = useState<Project[]>([]);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const isClient = f.role === "client";

  useEffect(() => {
    // Only needed to scope a client's access.
    api.projects().then(setProjects).catch(() => setProjects([]));
  }, []);

  function toggle(id: number) {
    setSelected((s) => {
      const n = new Set(s);
      n.has(id) ? n.delete(id) : n.add(id);
      return n;
    });
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr("");
    if (isClient && selected.size === 0) {
      setErr("Select at least one project this client can access.");
      return;
    }
    setBusy(true);
    try {
      onCreated(
        await api.createUser({
          ...f,
          project_ids: isClient ? [...selected] : [],
        })
      );
      onClose();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <form className="modal" onClick={(e) => e.stopPropagation()} onSubmit={submit}>
        <h2>Add user</h2>
        <label>Full name</label>
        <input value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} autoFocus required />
        <label>Email</label>
        <input type="email" value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} required />
        <label>Temporary password</label>
        <input value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} required minLength={6} />
        <label>Role</label>
        <select value={f.role} onChange={(e) => setF({ ...f, role: e.target.value as Role })}>
          {allowedRoles.map((r) => (
            <option key={r} value={r}>{ROLE_LABELS[r]}</option>
          ))}
        </select>

        {isClient && (
          <>
            <label>Project access (clients see only selected projects)</label>
            <div className="project-picker">
              {projects.length === 0 && <p className="muted">No projects available.</p>}
              {projects.map((p) => (
                <label key={p.id} className="check-row">
                  <input
                    type="checkbox"
                    checked={selected.has(p.id)}
                    onChange={() => toggle(p.id)}
                  />
                  <span>{p.name}</span>
                </label>
              ))}
            </div>
          </>
        )}

        {err && <div className="alert error">{err}</div>}
        <div className="modal-actions">
          <button type="button" className="btn ghost" onClick={onClose}>Cancel</button>
          <button className="btn primary" disabled={busy}>{busy ? "Creating…" : "Create user"}</button>
        </div>
      </form>
    </div>
  );
}
