import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api";
import { isDevAdmin, isDevTeam } from "../types";
import type {
  AIAnalysis,
  Deliverable,
  DeliverableFile,
  DeliverableStatus,
  ProjectDetail,
  User,
} from "../types";

const STATUSES: DeliverableStatus[] = [
  "pending", "in_progress", "submitted", "approved", "rejected",
];

function scoreClass(s: number) {
  if (s >= 75) return "score-good";
  if (s >= 50) return "score-mid";
  return "score-low";
}

function Lines({ text }: { text: string }) {
  const items = text.split("\n").map((l) => l.trim()).filter(Boolean);
  if (!items.length) return <span className="muted">—</span>;
  return (
    <ul className="ai-list">
      {items.map((l, i) => <li key={i}>{l}</li>)}
    </ul>
  );
}

export default function DeliverablesPanel({
  project,
  user,
}: {
  project: ProjectDetail;
  user: User;
}) {
  const isAdmin = isDevAdmin(user.role);   // can edit/assign
  const internal = isDevTeam(user.role);   // can see AI analysis
  const [items, setItems] = useState<Deliverable[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [openAI, setOpenAI] = useState<number | null>(null);
  const [openFiles, setOpenFiles] = useState<number | null>(null);
  const [analyzing, setAnalyzing] = useState<number | null>(null);

  async function load() {
    setLoading(true);
    try {
      setItems(await api.deliverables(project.id));
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    load();
    if (isAdmin) api.users().then(setUsers).catch(() => setUsers([]));
  }, [project.id]);

  const pointTitle = useMemo(() => {
    const m = new Map<number, string>();
    for (const p of project.plan_points) m.set(p.id, p.title);
    return m;
  }, [project.plan_points]);

  const grouped = useMemo(() => {
    const g = new Map<number | null, Deliverable[]>();
    for (const d of items) {
      if (!g.has(d.plan_point_id)) g.set(d.plan_point_id, []);
      g.get(d.plan_point_id)!.push(d);
    }
    return g;
  }, [items]);

  function patch(id: number, upd: Deliverable) {
    setItems((xs) => xs.map((x) => (x.id === id ? upd : x)));
  }

  async function setStatus(d: Deliverable, status: DeliverableStatus) {
    patch(d.id, await api.updateDeliverable(project.id, d.id, { status }));
  }
  async function toggleVisible(d: Deliverable) {
    patch(d.id, await api.updateDeliverable(project.id, d.id, {
      client_visible: d.client_visible ? 0 : 1,
    }));
  }
  async function assign(d: Deliverable, assignee_id: number | null) {
    patch(d.id, await api.updateDeliverable(project.id, d.id, { assignee_id }));
  }
  async function analyze(d: Deliverable) {
    setAnalyzing(d.id);
    try {
      const analysis: AIAnalysis = await api.analyzeDeliverable(project.id, d.id);
      patch(d.id, { ...d, latest_analysis: analysis });
      setOpenAI(d.id);
    } finally {
      setAnalyzing(null);
    }
  }
  async function submit(d: Deliverable) {
    patch(d.id, await api.submitDeliverable(project.id, d.id));
  }

  if (loading) return <div className="spinner" />;
  if (items.length === 0) {
    return (
      <div className="info-box">
        No deliverables yet. Submit the master plan in the <strong>Setup</strong>{" "}
        tab to auto-generate deliverables with AI.
      </div>
    );
  }

  return (
    <div>
      <div className="panel-head">
        <div>
          <h2>Deliverables</h2>
          <p className="muted">
            {internal
              ? "Deliverables generated from the master plan. AI analysis is internal-only."
              : "Your project deliverables. Upload documentation for anything assigned to you and submit it."}
          </p>
        </div>
      </div>

      {[...grouped.entries()].map(([pointId, list]) => (
        <div key={pointId ?? "none"} className="deliv-group">
          <h3 className="deliv-group-title">
            {pointId && pointTitle.get(pointId) ? pointTitle.get(pointId) : "Unassigned"}
          </h3>
          {list.map((d) => {
            const mine = d.assignee_id === user.id;
            return (
              <div key={d.id} className={`deliv-card ${mine ? "assigned-me" : ""}`}>
                <div className="deliv-main">
                  <div className="deliv-info">
                    <div className="deliv-title-row">
                      <span className="deliv-title">{d.title}</span>
                      {internal && d.ai_generated ? <span className="tag ai">AI</span> : null}
                      {internal && !d.client_visible ? <span className="tag hidden">internal</span> : null}
                      {mine ? <span className="tag mine">assigned to you</span> : null}
                    </div>
                    {d.description && <p className="deliv-desc">{d.description}</p>}
                    {d.acceptance_criteria && (
                      <p className="deliv-ac"><strong>Acceptance:</strong> {d.acceptance_criteria}</p>
                    )}
                    <div className="deliv-metaline">
                      {d.assignee_name && (
                        <span className="meta-assignee">👤 {d.assignee_name}</span>
                      )}
                      <button className="linkish" onClick={() => setOpenFiles(openFiles === d.id ? null : d.id)}>
                        📎 {d.file_count} file{d.file_count === 1 ? "" : "s"}
                      </button>
                    </div>
                  </div>

                  <div className="deliv-controls">
                    <select
                      value={d.status}
                      disabled={!isAdmin}
                      onChange={(e) => setStatus(d, e.target.value as DeliverableStatus)}
                      className={`status-select status-${d.status}`}
                    >
                      {STATUSES.map((s) => (
                        <option key={s} value={s}>{s.replace("_", " ")}</option>
                      ))}
                    </select>

                    {isAdmin && (
                      <select
                        className="status-select"
                        value={d.assignee_id ?? ""}
                        onChange={(e) => assign(d, e.target.value === "" ? null : Number(e.target.value))}
                        title="Assign to"
                      >
                        <option value="">Unassigned</option>
                        {users.map((u) => (
                          <option key={u.id} value={u.id}>{u.name}</option>
                        ))}
                      </select>
                    )}

                    {/* Client / assignee actions */}
                    {mine && d.status !== "submitted" && d.status !== "approved" && (
                      <button className="btn small primary" onClick={() => submit(d)}>
                        Submit
                      </button>
                    )}

                    {/* AI analysis — INTERNAL ONLY */}
                    {internal && (
                      <>
                        {d.latest_analysis && (
                          <div className={`score-chip ${scoreClass(d.latest_analysis.score)}`}>
                            {Math.round(d.latest_analysis.score)}<span className="score-of">/100</span>
                          </div>
                        )}
                        <button className="btn small" onClick={() => analyze(d)} disabled={analyzing === d.id}>
                          {analyzing === d.id ? "Analyzing…" : d.latest_analysis ? "Re-analyze" : "AI analysis"}
                        </button>
                        {d.latest_analysis && (
                          <button className="btn small ghost" onClick={() => setOpenAI(openAI === d.id ? null : d.id)}>
                            {openAI === d.id ? "Hide" : "View"}
                          </button>
                        )}
                      </>
                    )}
                    {isAdmin && (
                      <button className="btn small ghost" onClick={() => toggleVisible(d)} title="Toggle client visibility">
                        {d.client_visible ? "👁 client" : "🙈 internal"}
                      </button>
                    )}
                  </div>
                </div>

                {openFiles === d.id && (
                  <FileSection
                    projectId={project.id}
                    deliverable={d}
                    canUpload={isAdmin || mine}
                    onChange={(count) => patch(d.id, { ...d, file_count: count })}
                  />
                )}

                {internal && openAI === d.id && d.latest_analysis && (
                  <div className="ai-subpanel">
                    <div className="ai-subpanel-head">
                      <span className="ai-badge">
                        ✦ Grok analysis · internal only
                        {d.latest_analysis.is_mock ? " (mock — set GROK_API_KEY)" : ` · ${d.latest_analysis.model}`}
                      </span>
                      <span className={`score-chip lg ${scoreClass(d.latest_analysis.score)}`}>
                        {Math.round(d.latest_analysis.score)}<span className="score-of">/100 alignment</span>
                      </span>
                    </div>
                    <p className="ai-summary">{d.latest_analysis.summary}</p>
                    <div className="ai-grid">
                      <div><h4 className="ai-h strengths">Strengths</h4><Lines text={d.latest_analysis.strengths} /></div>
                      <div><h4 className="ai-h gaps">Gaps</h4><Lines text={d.latest_analysis.gaps} /></div>
                      <div><h4 className="ai-h recs">Recommendations</h4><Lines text={d.latest_analysis.recommendations} /></div>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      ))}
    </div>
  );
}

function FileSection({
  projectId, deliverable, canUpload, onChange,
}: {
  projectId: number;
  deliverable: Deliverable;
  canUpload: boolean;
  onChange: (count: number) => void;
}) {
  const [files, setFiles] = useState<DeliverableFile[]>([]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const input = useRef<HTMLInputElement>(null);

  async function load() {
    try {
      const fs = await api.deliverableFiles(projectId, deliverable.id);
      setFiles(fs);
      onChange(fs.length);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Could not load files");
    }
  }
  useEffect(() => { load(); }, [deliverable.id]);

  async function upload(list: FileList | null) {
    if (!list?.length) return;
    setBusy(true);
    setErr("");
    try {
      for (const f of Array.from(list)) {
        await api.uploadDeliverableFile(projectId, deliverable.id, f);
      }
      await load();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setBusy(false);
      if (input.current) input.current.value = "";
    }
  }

  async function remove(fileId: number) {
    await api.deleteDeliverableFile(projectId, deliverable.id, fileId);
    await load();
  }

  return (
    <div className="deliv-files">
      {files.length === 0 && <p className="muted">No documents uploaded yet.</p>}
      {files.map((f) => (
        <div key={f.id} className="file-row">
          <span className="file-name">📄 {f.filename}</span>
          <span className="file-meta">{(f.size / 1024).toFixed(0)} KB</span>
          <div className="file-actions">
            <button className="btn small ghost" onClick={() => api.downloadDeliverableFile(projectId, deliverable.id, f)}>
              Download
            </button>
            {canUpload && (
              <button className="btn small ghost" onClick={() => remove(f.id)}>Remove</button>
            )}
          </div>
        </div>
      ))}
      {err && <div className="alert error">{err}</div>}
      {canUpload && (
        <div className="deliv-upload">
          <input ref={input} type="file" multiple hidden onChange={(e) => upload(e.target.files)} />
          <button className="btn small" onClick={() => input.current?.click()} disabled={busy}>
            {busy ? "Uploading…" : "+ Upload document"}
          </button>
        </div>
      )}
    </div>
  );
}
