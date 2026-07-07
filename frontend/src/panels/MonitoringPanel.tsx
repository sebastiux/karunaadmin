import { useEffect, useState } from "react";
import { api } from "../api";
import type { MonitoringOverview } from "../types";

function Ring({ value }: { value: number }) {
  const r = 52;
  const c = 2 * Math.PI * r;
  const offset = c - (value / 100) * c;
  const color = value >= 75 ? "#22c55e" : value >= 40 ? "#f59e0b" : "#ef4444";
  return (
    <svg className="ring" viewBox="0 0 120 120" width={120} height={120}>
      <circle cx="60" cy="60" r={r} className="ring-track" />
      <circle
        cx="60" cy="60" r={r}
        stroke={color}
        strokeWidth="10"
        fill="none"
        strokeLinecap="round"
        strokeDasharray={c}
        strokeDashoffset={offset}
        transform="rotate(-90 60 60)"
      />
      <text x="60" y="66" textAnchor="middle" className="ring-text">
        {Math.round(value)}%
      </text>
    </svg>
  );
}

export default function MonitoringPanel({ projectId }: { projectId: number }) {
  const [data, setData] = useState<MonitoringOverview | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    api.monitoring(projectId).then(setData).finally(() => setLoading(false));
  }, [projectId]);

  if (loading) return <div className="spinner" />;
  if (!data) return <div className="info-box">No monitoring data.</div>;

  return (
    <div className="monitoring">
      <div className="mon-hero">
        <Ring value={data.overall_progress} />
        <div className="mon-hero-stats">
          <h2>Overall progress</h2>
          <p className="muted">A non-technical view of how the project is tracking against its plan.</p>
          <div className="stat-row">
            <div className="stat">
              <div className="stat-num">{data.completed_deliverables}/{data.total_deliverables}</div>
              <div className="stat-label">Deliverables done</div>
            </div>
            <div className="stat">
              <div className="stat-num">{data.points.length}</div>
              <div className="stat-label">Plan objectives</div>
            </div>
            <div className="stat">
              <div className="stat-num">
                {data.avg_ai_score != null ? `${Math.round(data.avg_ai_score)}` : "—"}
                {data.avg_ai_score != null && <span className="stat-of">/100</span>}
              </div>
              <div className="stat-label">Avg AI alignment</div>
            </div>
          </div>
        </div>
      </div>

      <h3 className="mon-section">Progress by objective</h3>
      <div className="mon-points">
        {data.points.map((p) => (
          <div key={p.plan_point_id} className="mon-point">
            <div className="mon-point-head">
              <span className="mon-point-title">{p.title}</span>
              <span className="mon-point-frac">
                {p.completed_deliverables}/{p.total_deliverables}
              </span>
            </div>
            <div className="progress-track">
              <div
                className="progress-fill"
                style={{
                  width: `${p.progress}%`,
                  background:
                    p.progress >= 75 ? "#22c55e" : p.progress >= 40 ? "#f59e0b" : "#6366f1",
                }}
              />
            </div>
            <div className="mon-point-foot">
              <span>{Math.round(p.progress)}% complete</span>
              {p.avg_ai_score != null && (
                <span className="mon-ai">AI alignment {Math.round(p.avg_ai_score)}/100</span>
              )}
            </div>
          </div>
        ))}
        {data.points.length === 0 && (
          <div className="info-box">
            No objectives yet — submit the master plan to populate this view.
          </div>
        )}
      </div>
    </div>
  );
}
