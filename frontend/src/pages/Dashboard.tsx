import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import { isDevAdmin, type Project } from "../types";
import { useAuth } from "../auth";

export default function Dashboard() {
  const { user } = useAuth();
  const nav = useNavigate();
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [showNew, setShowNew] = useState(false);
  const [name, setName] = useState("");
  const [desc, setDesc] = useState("");
  const [err, setErr] = useState("");

  async function load() {
    setLoading(true);
    try {
      setProjects(await api.projects());
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    load();
  }, []);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    setErr("");
    try {
      const p = await api.createProject(name, desc);
      setShowNew(false);
      setName("");
      setDesc("");
      nav(`/projects/${p.id}`);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Failed");
    }
  }

  return (
    <div className="container">
      <div className="page-head">
        <div>
          <h1>Projects</h1>
          <p className="muted">Administer projects across code review, deliverables and client monitoring.</p>
        </div>
        {isDevAdmin(user?.role) && (
          <button className="btn primary" onClick={() => setShowNew(true)}>
            + New project
          </button>
        )}
      </div>

      {loading ? (
        <div className="spinner" />
      ) : projects.length === 0 ? (
        <div className="empty-state">
          <p>No projects yet.</p>
          {isDevAdmin(user?.role) && (
            <button className="btn primary" onClick={() => setShowNew(true)}>
              Create your first project
            </button>
          )}
        </div>
      ) : (
        <div className="project-grid">
          {projects.map((p) => (
            <div
              key={p.id}
              className="project-card"
              onClick={() => nav(`/projects/${p.id}`)}
            >
              <div className="project-card-head">
                <h3>{p.name}</h3>
                <span className={`status-pill status-${p.status}`}>{p.status}</span>
              </div>
              <p className="muted clamp">{p.description || "No description"}</p>
              <div className="project-card-foot">
                Updated {new Date(p.updated_at).toLocaleDateString()}
              </div>
            </div>
          ))}
        </div>
      )}

      {showNew && (
        <div className="modal-backdrop" onClick={() => setShowNew(false)}>
          <form
            className="modal"
            onClick={(e) => e.stopPropagation()}
            onSubmit={create}
          >
            <h2>New project</h2>
            <label>Name</label>
            <input value={name} onChange={(e) => setName(e.target.value)} autoFocus required />
            <label>Description</label>
            <textarea value={desc} onChange={(e) => setDesc(e.target.value)} rows={3} />
            {err && <div className="alert error">{err}</div>}
            <div className="modal-actions">
              <button type="button" className="btn ghost" onClick={() => setShowNew(false)}>
                Cancel
              </button>
              <button className="btn primary">Create</button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
