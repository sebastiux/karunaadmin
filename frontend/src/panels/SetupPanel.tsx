import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import type { ProjectDetail, ProjectFile } from "../types";

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
  const [files, setFiles] = useState<ProjectFile[]>([]);
  const [uploading, setUploading] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);
  const configured = project.plan_points.length > 0;

  useEffect(() => {
    api.files(project.id).then(setFiles).catch(() => setFiles([]));
  }, [project.id]);

  async function submit() {
    if (!plan.trim()) {
      setErr("Add the master plan text, or upload a document to extract it.");
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

  async function onFiles(list: FileList | null) {
    if (!list || list.length === 0) return;
    setErr("");
    setUploading(true);
    try {
      let appended = "";
      for (const file of Array.from(list)) {
        const res = await api.uploadFile(project.id, file);
        setFiles((fs) => [res.file, ...fs.filter((f) => f.id !== res.file.id)]);
        if (res.extracted_text.trim()) {
          appended += (appended ? "\n\n" : "") + res.extracted_text.trim();
        }
      }
      if (appended) {
        setPlan((p) => (p.trim() ? `${p.trim()}\n\n${appended}` : appended));
      } else {
        setErr("File stored, but no text could be extracted (image-only PDF?). You can still type the plan.");
      }
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setUploading(false);
      if (fileInput.current) fileInput.current.value = "";
    }
  }

  async function removeFile(id: number) {
    await api.deleteFile(project.id, id);
    setFiles((fs) => fs.filter((f) => f.id !== id));
  }

  if (!isAdmin) {
    return (
      <div className="info-box">
        Project configuration is managed by dev admins. The master plan for this
        project has {configured ? "been submitted" : "not yet been submitted"}.
        {files.length > 0 && (
          <div className="file-list" style={{ marginTop: 14 }}>
            {files.map((f) => (
              <div key={f.id} className="file-row">
                <span className="file-name">{f.filename}</span>
                <button className="btn small ghost" onClick={() => api.downloadFile(project.id, f)}>
                  Download
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="setup">
      <div className="setup-intro">
        <h2>Step 1 · Submit the master plan</h2>
        <p className="muted">
          Upload the plan as a document (PDF, DOCX, TXT…) or paste it below. The AI
          (Grok) parses it into objectives and generates the client deliverables.
          Re-submitting regenerates AI deliverables (manual ones are kept).
        </p>
      </div>

      {/* Upload zone */}
      <div
        className={`dropzone ${uploading ? "uploading" : ""}`}
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => {
          e.preventDefault();
          onFiles(e.dataTransfer.files);
        }}
        onClick={() => fileInput.current?.click()}
      >
        <input
          ref={fileInput}
          type="file"
          multiple
          hidden
          onChange={(e) => onFiles(e.target.files)}
        />
        {uploading ? (
          <span>Uploading & extracting text…</span>
        ) : (
          <span>
            <strong>Click to upload</strong> or drag files here — PDF, DOCX, TXT, or any document
          </span>
        )}
      </div>

      {files.length > 0 && (
        <div className="file-list">
          {files.map((f) => (
            <div key={f.id} className="file-row">
              <span className="file-name">📄 {f.filename}</span>
              <span className="file-meta">
                {(f.size / 1024).toFixed(0)} KB ·{" "}
                {f.extracted_chars > 0 ? `${f.extracted_chars} chars extracted` : "no text"}
              </span>
              <div className="file-actions">
                <button className="btn small ghost" onClick={() => api.downloadFile(project.id, f)}>
                  Download
                </button>
                <button className="btn small ghost" onClick={() => removeFile(f.id)}>
                  Remove
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      <textarea
        className="plan-input"
        placeholder={
          "Master plan text — uploaded document text lands here automatically, or type it:\n1. …\n2. …"
        }
        value={plan}
        onChange={(e) => setPlan(e.target.value)}
        rows={14}
      />

      {err && <div className="alert error">{err}</div>}

      <div className="setup-actions">
        <button className="btn primary" onClick={submit} disabled={busy}>
          {busy
            ? "Analyzing plan & generating deliverables…"
            : configured
            ? "Re-generate deliverables"
            : "Generate deliverables"}
        </button>
        {configured && (
          <span className="muted">{project.plan_points.length} objectives currently generated.</span>
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
