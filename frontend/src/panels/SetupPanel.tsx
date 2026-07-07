import { useState } from "react";
import { api } from "../api";
import type { ProjectDetail } from "../types";

export default function SetupPanel({
  project,
  isAdmin,
  onSaved,
}: {
  project: ProjectDetail;
  isAdmin: boolean;
  onSaved: () => void;
}) {
  const [plan, setPlan] = useState(project.master_plan);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const configured = project.plan_points.length > 0;

  async function submit() {
    if (!plan.trim()) {
      setErr("Please paste the master plan first.");
      return;
    }
    setErr("");
    setBusy(true);
    try {
      await api.submitMasterPlan(project.id, plan);
      onSaved();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Failed to process plan");
    } finally {
      setBusy(false);
    }
  }

  if (!isAdmin) {
    return (
      <div className="info-box">
        Project configuration is managed by administrators. The master plan for
        this project has {configured ? "been submitted" : "not yet been submitted"}.
      </div>
    );
  }

  return (
    <div className="setup">
      <div className="setup-intro">
        <h2>Step 1 · Submit the master plan</h2>
        <p className="muted">
          Paste the project master plan below. The AI (Grok) parses it into
          objectives and automatically generates the client deliverables for each.
          Re-submitting regenerates AI deliverables (manually-added ones are kept).
        </p>
      </div>

      <textarea
        className="plan-input"
        placeholder={
          "e.g.\n1. Redesign the marketing homepage\n2. Build the checkout & payments flow\n3. Launch analytics dashboard\n..."
        }
        value={plan}
        onChange={(e) => setPlan(e.target.value)}
        rows={14}
      />

      {err && <div className="alert error">{err}</div>}

      <div className="setup-actions">
        <button className="btn primary" onClick={submit} disabled={busy}>
          {busy ? "Analyzing plan & generating deliverables…" : configured ? "Re-generate deliverables" : "Generate deliverables"}
        </button>
        {configured && (
          <span className="muted">
            {project.plan_points.length} objectives currently generated.
          </span>
        )}
      </div>

      {configured && (
        <div className="plan-points">
          <h3>Generated objectives</h3>
          <ol>
            {project.plan_points.map((p) => (
              <li key={p.id}>
                <strong>{p.title}</strong>
                {p.description && p.description !== p.title && (
                  <p className="muted">{p.description}</p>
                )}
              </li>
            ))}
          </ol>
        </div>
      )}
    </div>
  );
}
