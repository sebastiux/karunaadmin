import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import type { AIAnalysis, Deliverable, DeliverableStatus, ProjectDetail } from "../types";

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
  isAdmin,
}: {
  project: ProjectDetail;
  isAdmin: boolean;
}) {
  const [items, setItems] = useState<Deliverable[]>([]);
  const [loading, setLoading] = useState(true);
  const [openAI, setOpenAI] = useState<number | null>(null);
  const [analyzing, setAnalyzing] = useState<number | null>(null);

  async function load() {
    setLoading(true);
    try {
      setItems(await api.deliverables(project.id));
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => { load(); }, [project.id]);

  const pointTitle = useMemo(() => {
    const m = new Map<number, string>();
    for (const p of project.plan_points) m.set(p.id, p.title);
    return m;
  }, [project.plan_points]);

  const grouped = useMemo(() => {
    const g = new Map<number | null, Deliverable[]>();
    for (const d of items) {
      const key = d.plan_point_id;
      if (!g.has(key)) g.set(key, []);
      g.get(key)!.push(d);
    }
    return g;
  }, [items]);

  async function setStatus(d: Deliverable, status: DeliverableStatus) {
    const updated = await api.updateDeliverable(project.id, d.id, { status });
    setItems((xs) => xs.map((x) => (x.id === d.id ? updated : x)));
  }

  async function toggleVisible(d: Deliverable) {
    const updated = await api.updateDeliverable(project.id, d.id, {
      client_visible: d.client_visible ? 0 : 1,
    });
    setItems((xs) => xs.map((x) => (x.id === d.id ? updated : x)));
  }

  async function analyze(d: Deliverable) {
    setAnalyzing(d.id);
    try {
      const analysis: AIAnalysis = await api.analyzeDeliverable(project.id, d.id);
      setItems((xs) =>
        xs.map((x) => (x.id === d.id ? { ...x, latest_analysis: analysis } : x))
      );
      setOpenAI(d.id);
    } finally {
      setAnalyzing(null);
    }
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
            Client deliverables generated from the master plan. Open{" "}
            <strong>AI analysis</strong> to score each against the plan (Grok).
          </p>
        </div>
      </div>

      {[...grouped.entries()].map(([pointId, list]) => (
        <div key={pointId ?? "none"} className="deliv-group">
          <h3 className="deliv-group-title">
            {pointId && pointTitle.get(pointId) ? pointTitle.get(pointId) : "Unassigned"}
          </h3>
          {list.map((d) => (
            <div key={d.id} className="deliv-card">
              <div className="deliv-main">
                <div className="deliv-info">
                  <div className="deliv-title-row">
                    <span className="deliv-title">{d.title}</span>
                    {d.ai_generated ? <span className="tag ai">AI</span> : null}
                    {!d.client_visible ? <span className="tag hidden">internal</span> : null}
                  </div>
                  {d.description && <p className="deliv-desc">{d.description}</p>}
                  {d.acceptance_criteria && (
                    <p className="deliv-ac">
                      <strong>Acceptance:</strong> {d.acceptance_criteria}
                    </p>
                  )}
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
                  {d.latest_analysis && (
                    <div className={`score-chip ${scoreClass(d.latest_analysis.score)}`}>
                      {Math.round(d.latest_analysis.score)}
                      <span className="score-of">/100</span>
                    </div>
                  )}
                  <button
                    className="btn small"
                    onClick={() => analyze(d)}
                    disabled={analyzing === d.id}
                  >
                    {analyzing === d.id ? "Analyzing…" : d.latest_analysis ? "Re-analyze" : "AI analysis"}
                  </button>
                  {d.latest_analysis && (
                    <button
                      className="btn small ghost"
                      onClick={() => setOpenAI(openAI === d.id ? null : d.id)}
                    >
                      {openAI === d.id ? "Hide" : "View"}
                    </button>
                  )}
                  {isAdmin && (
                    <button
                      className="btn small ghost"
                      onClick={() => toggleVisible(d)}
                      title="Toggle client visibility"
                    >
                      {d.client_visible ? "👁 client" : "🙈 internal"}
                    </button>
                  )}
                </div>
              </div>

              {openAI === d.id && d.latest_analysis && (
                <div className="ai-subpanel">
                  <div className="ai-subpanel-head">
                    <span className="ai-badge">
                      ✦ Grok analysis
                      {d.latest_analysis.is_mock ? " (mock — set GROK_API_KEY)" : ` · ${d.latest_analysis.model}`}
                    </span>
                    <span className={`score-chip lg ${scoreClass(d.latest_analysis.score)}`}>
                      {Math.round(d.latest_analysis.score)}<span className="score-of">/100 alignment</span>
                    </span>
                  </div>
                  <p className="ai-summary">{d.latest_analysis.summary}</p>
                  <div className="ai-grid">
                    <div>
                      <h4 className="ai-h strengths">Strengths</h4>
                      <Lines text={d.latest_analysis.strengths} />
                    </div>
                    <div>
                      <h4 className="ai-h gaps">Gaps</h4>
                      <Lines text={d.latest_analysis.gaps} />
                    </div>
                    <div>
                      <h4 className="ai-h recs">Recommendations</h4>
                      <Lines text={d.latest_analysis.recommendations} />
                    </div>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}
