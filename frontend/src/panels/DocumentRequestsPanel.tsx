import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { isDevTeam } from "../types";
import type { DocRequest, DocRequestStatus, User } from "../types";

const STATUS_LABEL: Record<DocRequestStatus, string> = {
  open: "Awaiting upload",
  submitted: "Submitted",
  fulfilled: "Fulfilled",
};

export default function DocumentRequestsPanel({
  project,
  user,
}: {
  project: { id: number; name: string };
  user: User;
}) {
  const internal = isDevTeam(user.role);
  const [requests, setRequests] = useState<DocRequest[]>([]);
  const [clients, setClients] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [compose, setCompose] = useState(false);

  async function load() {
    setLoading(true);
    try {
      setRequests(await api.docRequests(project.id));
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    load();
    if (internal)
      api.projectMembers(project.id)
        .then((m) => setClients(m.filter((u) => u.role === "client")))
        .catch(() => setClients([]));
  }, [project.id]);

  if (loading) return <div className="spinner" />;

  return (
    <div>
      <div className="panel-head">
        <div>
          <h2>Requested documents</h2>
          <p className="muted">
            {internal
              ? "Request documents from client users on this project. They're emailed and upload here."
              : "Documents the team has requested from you. Upload the files for each request."}
          </p>
        </div>
        {internal && (
          <button className="btn primary" onClick={() => setCompose(true)}>
            + Request document
          </button>
        )}
      </div>

      {requests.length === 0 ? (
        <div className="info-box">
          {internal
            ? "No document requests yet."
            : "No documents have been requested from you."}
        </div>
      ) : (
        <div className="req-list">
          {requests.map((r) => (
            <RequestCard
              key={r.id}
              projectId={project.id}
              req={r}
              internal={internal}
              onChange={load}
            />
          ))}
        </div>
      )}

      {compose && (
        <Composer
          projectId={project.id}
          clients={clients}
          onClose={() => setCompose(false)}
          onCreated={() => {
            setCompose(false);
            load();
          }}
        />
      )}
    </div>
  );
}

function RequestCard({
  projectId, req, internal, onChange,
}: {
  projectId: number;
  req: DocRequest;
  internal: boolean;
  onChange: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const input = useRef<HTMLInputElement>(null);

  async function upload(list: FileList | null) {
    if (!list?.length) return;
    setBusy(true);
    try {
      for (const f of Array.from(list)) {
        await api.uploadDocRequestFile(projectId, req.id, f);
      }
      onChange();
    } finally {
      setBusy(false);
      if (input.current) input.current.value = "";
    }
  }

  return (
    <div className="req-card">
      <div className="req-head">
        <div>
          <span className="req-title">{req.title}</span>
          <span className={`req-status st-${req.status}`}>{STATUS_LABEL[req.status]}</span>
        </div>
        {internal && (
          <div className="req-admin">
            {req.recipient_names.length > 0 && (
              <span className="muted small">requested from {req.recipient_names.join(", ")}</span>
            )}
            {req.status === "submitted" && (
              <button
                className="btn small"
                onClick={async () => { await api.setDocRequestStatus(projectId, req.id, "fulfilled"); onChange(); }}
              >
                Mark fulfilled
              </button>
            )}
            <button
              className="btn small ghost"
              onClick={async () => { if (confirm("Delete this request?")) { await api.deleteDocRequest(projectId, req.id); onChange(); } }}
            >
              Delete
            </button>
          </div>
        )}
      </div>
      {req.description && <p className="req-desc">{req.description}</p>}

      <div className="req-files">
        {req.files.length === 0 && <p className="muted small">No documents uploaded yet.</p>}
        {req.files.map((f) => (
          <div key={f.id} className="file-row">
            <span className="file-name">📄 {f.filename}</span>
            <span className="file-meta">{(f.size / 1024).toFixed(0)} KB</span>
            <div className="file-actions">
              <button className="btn small ghost" onClick={() => api.downloadDocRequestFile(projectId, req.id, f)}>
                Download
              </button>
            </div>
          </div>
        ))}
      </div>

      {/* Both the client (recipient) and internal team can attach files */}
      <div className="req-upload">
        <input ref={input} type="file" multiple hidden onChange={(e) => upload(e.target.files)} />
        <button className="btn small primary" onClick={() => input.current?.click()} disabled={busy}>
          {busy ? "Uploading…" : "+ Upload document"}
        </button>
      </div>
    </div>
  );
}

function Composer({
  projectId, clients, onClose, onCreated,
}: {
  projectId: number;
  clients: User[];
  onClose: () => void;
  onCreated: () => void;
}) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  function toggle(id: number) {
    setSelected((s) => {
      const n = new Set(s);
      n.has(id) ? n.delete(id) : n.add(id);
      return n;
    });
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (selected.size === 0) {
      setErr("Select at least one client to request from.");
      return;
    }
    setErr("");
    setBusy(true);
    try {
      await api.createDocRequest(projectId, {
        title,
        description,
        recipient_user_ids: [...selected],
      });
      onCreated();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <form className="modal" onClick={(e) => e.stopPropagation()} onSubmit={submit}>
        <h2>Request a document</h2>
        <label>What do you need?</label>
        <input value={title} onChange={(e) => setTitle(e.target.value)} autoFocus required placeholder="e.g. Signed contract, ID scan…" />
        <label>Details (optional)</label>
        <textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={3} />
        <label>Request from (client users on this project — they'll be emailed)</label>
        <div className="project-picker">
          {clients.length === 0 && (
            <p className="muted">No client users on this project yet. Add a client with access to this project first.</p>
          )}
          {clients.map((u) => (
            <label key={u.id} className="check-row">
              <input type="checkbox" checked={selected.has(u.id)} onChange={() => toggle(u.id)} />
              <span>{u.name} <span className="muted">· {u.email}</span></span>
            </label>
          ))}
        </div>
        {err && <div className="alert error">{err}</div>}
        <div className="modal-actions">
          <button type="button" className="btn ghost" onClick={onClose}>Cancel</button>
          <button className="btn primary" disabled={busy}>{busy ? "Sending…" : "Send request"}</button>
        </div>
      </form>
    </div>
  );
}
