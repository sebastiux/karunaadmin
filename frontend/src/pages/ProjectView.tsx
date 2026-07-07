import { useEffect, useState, useCallback } from "react";
import { useParams, Link } from "react-router-dom";
import { api } from "../api";
import { isDevAdmin, type ProjectDetail } from "../types";
import { useAuth } from "../auth";
import SetupPanel from "../panels/SetupPanel";
import CodeReviewPanel from "../panels/CodeReviewPanel";
import DeliverablesPanel from "../panels/DeliverablesPanel";
import MonitoringPanel from "../panels/MonitoringPanel";

type TabId = "setup" | "code" | "deliverables" | "monitoring";

const TABS: { id: TabId; label: string; hint: string }[] = [
  { id: "setup", label: "① Setup", hint: "Master plan" },
  { id: "code", label: "Code Review", hint: "Kanban board" },
  { id: "deliverables", label: "Deliverables", hint: "Client + AI analysis" },
  { id: "monitoring", label: "Client Monitoring", hint: "Visual progress" },
];

export default function ProjectView() {
  const { id } = useParams();
  const projectId = Number(id);
  const { user } = useAuth();
  const [project, setProject] = useState<ProjectDetail | null>(null);
  const [tab, setTab] = useState<TabId>("setup");
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const p = await api.project(projectId);
      setProject(p);
      // Jump straight to monitoring once the project is configured.
      setTab((t) => (t === "setup" && p.plan_points.length > 0 ? "deliverables" : t));
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    load();
  }, [load]);

  if (loading && !project) return <div className="container"><div className="spinner" /></div>;
  if (!project) return <div className="container">Project not found.</div>;

  return (
    <div className="container">
      <div className="breadcrumb">
        <Link to="/">Projects</Link> <span>/</span> <strong>{project.name}</strong>
      </div>
      <div className="page-head">
        <div>
          <h1>{project.name}</h1>
          <p className="muted">{project.description || "No description"}</p>
        </div>
        <span className={`status-pill status-${project.status}`}>{project.status}</span>
      </div>

      <nav className="tabs">
        {TABS.map((t) => (
          <button
            key={t.id}
            className={`tab ${tab === t.id ? "active" : ""}`}
            onClick={() => setTab(t.id)}
          >
            <span className="tab-label">{t.label}</span>
            <span className="tab-hint">{t.hint}</span>
          </button>
        ))}
      </nav>

      <section className="panel">
        {tab === "setup" && (
          <SetupPanel project={project} isAdmin={isDevAdmin(user?.role)} onSaved={load} />
        )}
        {tab === "code" && <CodeReviewPanel projectId={projectId} />}
        {tab === "deliverables" && (
          <DeliverablesPanel project={project} isAdmin={isDevAdmin(user?.role)} />
        )}
        {tab === "monitoring" && <MonitoringPanel projectId={projectId} />}
      </section>
    </div>
  );
}
