import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api";
import AuthImage from "../components/AuthImage";
import type { KanbanCard, KanbanCardImage, KanbanColumnId, User } from "../types";

const COLUMNS: { id: KanbanColumnId; label: string }[] = [
  { id: "backlog", label: "Backlog" },
  { id: "todo", label: "To do" },
  { id: "in_progress", label: "In progress" },
  { id: "in_review", label: "In review" },
  { id: "done", label: "Done" },
];

const PRIORITY_ORDER = { high: 0, medium: 1, low: 2 } as const;

export default function CodeReviewPanel({ projectId }: { projectId: number }) {
  const [cards, setCards] = useState<KanbanCard[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [dragId, setDragId] = useState<number | null>(null);
  const [overCol, setOverCol] = useState<KanbanColumnId | null>(null);
  const [composeCol, setComposeCol] = useState<KanbanColumnId | null>(null);
  const [editing, setEditing] = useState<KanbanCard | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  async function load() {
    setCards(await api.cards(projectId));
  }

  useEffect(() => {
    load();
    api.users().then(setUsers).catch(() => setUsers([]));
  }, [projectId]);

  // Optional realtime: refresh the board when a teammate changes it.
  useEffect(() => {
    const base = import.meta.env.VITE_REALTIME_URL;
    if (!base) return;
    try {
      const ws = new WebSocket(`${base}?room=project-${projectId}`);
      wsRef.current = ws;
      ws.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data);
          if (msg.type === "board:changed" && msg.senderRefresh !== false) load();
        } catch {
          /* ignore */
        }
      };
      return () => ws.close();
    } catch {
      /* realtime is best-effort */
    }
  }, [projectId]);

  function broadcast() {
    wsRef.current?.readyState === WebSocket.OPEN &&
      wsRef.current.send(
        JSON.stringify({ type: "board:changed", room: `project-${projectId}` })
      );
  }

  const byColumn = useMemo(() => {
    const map: Record<KanbanColumnId, KanbanCard[]> = {
      backlog: [], todo: [], in_progress: [], in_review: [], done: [],
    };
    for (const c of cards) map[c.column].push(c);
    for (const col of Object.keys(map) as KanbanColumnId[]) {
      map[col].sort(
        (a, b) => PRIORITY_ORDER[a.priority] - PRIORITY_ORDER[b.priority] || a.order - b.order
      );
    }
    return map;
  }, [cards]);

  async function drop(col: KanbanColumnId) {
    setOverCol(null);
    if (dragId == null) return;
    const card = cards.find((c) => c.id === dragId);
    setDragId(null);
    if (!card || card.column === col) return;
    // optimistic
    setCards((cs) => cs.map((c) => (c.id === card.id ? { ...c, column: col } : c)));
    await api.moveCard(projectId, card.id, col);
    broadcast();
  }

  async function remove(id: number) {
    setCards((cs) => cs.filter((c) => c.id !== id));
    await api.deleteCard(projectId, id);
    broadcast();
  }

  return (
    <div className="kanban-wrap">
      <div className="panel-head">
        <div>
          <h2>Code Review board</h2>
          <p className="muted">
            AI-free Kanban for developer follow-up. Drag cards between columns.
          </p>
        </div>
        <button className="btn primary" onClick={() => setComposeCol("backlog")}>
          + Add card
        </button>
      </div>

      <div className="board">
        {COLUMNS.map((col) => (
          <div
            key={col.id}
            className={`board-col ${overCol === col.id ? "drop-over" : ""}`}
            onDragOver={(e) => {
              e.preventDefault();
              setOverCol(col.id);
            }}
            onDragLeave={() => setOverCol((c) => (c === col.id ? null : c))}
            onDrop={() => drop(col.id)}
          >
            <div className="board-col-head">
              <span>{col.label}</span>
              <span className="count">{byColumn[col.id].length}</span>
            </div>
            <div className="board-col-body">
              {byColumn[col.id].map((card) => (
                <div
                  key={card.id}
                  className="kcard"
                  draggable
                  onDragStart={() => setDragId(card.id)}
                  onDragEnd={() => setDragId(null)}
                >
                  <div className="kcard-top">
                    <span className="ticket-no">{card.ticket_number}</span>
                    <span className={`prio prio-${card.priority}`}>{card.priority}</span>
                    <div className="kcard-actions">
                      <button className="kcard-edit" onClick={() => setEditing(card)} title="Edit">✎</button>
                      <button className="kcard-del" onClick={() => remove(card.id)} title="Delete">×</button>
                    </div>
                  </div>
                  <div className="kcard-title" onClick={() => setEditing(card)}>{card.title}</div>
                  {card.description && <div className="kcard-desc">{card.description}</div>}
                  <div className="kcard-foot">
                    {card.assignee_name && <span className="assignee">{card.assignee_name}</span>}
                    {card.image_count > 0 && <span className="img-badge">🖼 {card.image_count}</span>}
                    {card.pr_url && (
                      <a href={card.pr_url} target="_blank" rel="noreferrer" className="pr-link">
                        PR ↗
                      </a>
                    )}
                  </div>
                </div>
              ))}
              <button className="add-in-col" onClick={() => setComposeCol(col.id)}>
                + Add
              </button>
            </div>
          </div>
        ))}
      </div>

      {composeCol && (
        <CardComposer
          projectId={projectId}
          column={composeCol}
          users={users}
          onClose={() => setComposeCol(null)}
          onCreated={(c) => {
            setCards((cs) => [...cs, c]);
            broadcast();
          }}
        />
      )}

      {editing && (
        <CardEditor
          projectId={projectId}
          card={editing}
          users={users}
          onClose={() => setEditing(null)}
          onSaved={(c) => {
            setCards((cs) => cs.map((x) => (x.id === c.id ? c : x)));
            broadcast();
          }}
        />
      )}
    </div>
  );
}

function CardComposer({
  projectId,
  column,
  users,
  onClose,
  onCreated,
}: {
  projectId: number;
  column: KanbanColumnId;
  users: User[];
  onClose: () => void;
  onCreated: (c: KanbanCard) => void;
}) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [priority, setPriority] = useState<"low" | "medium" | "high">("medium");
  const [assignee, setAssignee] = useState<number | "">("");
  const [prUrl, setPrUrl] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      const c = await api.createCard(projectId, {
        title,
        description,
        column,
        priority,
        pr_url: prUrl,
        assignee_id: assignee === "" ? null : Number(assignee),
      });
      onCreated(c);
      onClose();
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <form className="modal" onClick={(e) => e.stopPropagation()} onSubmit={submit}>
        <h2>New card · {column.replace("_", " ")}</h2>
        <label>Title</label>
        <input value={title} onChange={(e) => setTitle(e.target.value)} autoFocus required />
        <label>Description</label>
        <textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={3} />
        <div className="form-row">
          <div>
            <label>Priority</label>
            <select value={priority} onChange={(e) => setPriority(e.target.value as any)}>
              <option value="high">High</option>
              <option value="medium">Medium</option>
              <option value="low">Low</option>
            </select>
          </div>
          <div>
            <label>Assignee</label>
            <select value={assignee} onChange={(e) => setAssignee(e.target.value === "" ? "" : Number(e.target.value))}>
              <option value="">Unassigned</option>
              {users.map((u) => (
                <option key={u.id} value={u.id}>{u.name}</option>
              ))}
            </select>
          </div>
        </div>
        <label>Pull request URL (optional)</label>
        <input value={prUrl} onChange={(e) => setPrUrl(e.target.value)} placeholder="https://github.com/…/pull/12" />
        <div className="modal-actions">
          <button type="button" className="btn ghost" onClick={onClose}>Cancel</button>
          <button className="btn primary" disabled={busy}>{busy ? "Adding…" : "Add card"}</button>
        </div>
      </form>
    </div>
  );
}

function CardEditor({
  projectId, card, users, onClose, onSaved,
}: {
  projectId: number;
  card: KanbanCard;
  users: User[];
  onClose: () => void;
  onSaved: (c: KanbanCard) => void;
}) {
  const [f, setF] = useState({
    title: card.title,
    description: card.description,
    column: card.column,
    priority: card.priority,
    pr_url: card.pr_url,
    assignee: (card.assignee_id ?? "") as number | "",
  });
  const [images, setImages] = useState<KanbanCardImage[]>([]);
  const [busy, setBusy] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [note, setNote] = useState("");
  const fileInput = useRef<HTMLInputElement>(null);

  async function loadImages() {
    setImages(await api.cardImages(projectId, card.id));
  }
  useEffect(() => { loadImages(); }, [card.id]);

  async function uploadFiles(files: (File | Blob)[]) {
    if (!files.length) return;
    setUploading(true);
    setNote("");
    try {
      for (const file of files) await api.uploadCardImage(projectId, card.id, file);
      await loadImages();
    } catch (e) {
      setNote(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  }

  // Paste a screenshot straight from the clipboard.
  async function onPaste(e: React.ClipboardEvent) {
    const imgs: File[] = [];
    for (const item of Array.from(e.clipboardData.items)) {
      if (item.type.startsWith("image/")) {
        const file = item.getAsFile();
        if (file) imgs.push(file);
      }
    }
    if (imgs.length) {
      e.preventDefault();
      await uploadFiles(imgs);
      setNote(`Pasted ${imgs.length} image${imgs.length > 1 ? "s" : ""}.`);
    }
  }

  async function removeImage(id: number) {
    await api.deleteCardImage(projectId, card.id, id);
    await loadImages();
  }

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      const updated = await api.updateCard(projectId, card.id, {
        title: f.title,
        description: f.description,
        column: f.column,
        priority: f.priority,
        pr_url: f.pr_url,
        assignee_id: f.assignee === "" ? null : Number(f.assignee),
      });
      onSaved(updated);
      onClose();
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <form className="modal wide" onClick={(e) => e.stopPropagation()} onSubmit={save} onPaste={onPaste}>
        <h2>{card.ticket_number} · Edit card</h2>
        <label>Title</label>
        <input value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} required />
        <label>Description</label>
        <textarea value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} rows={3} />
        <div className="form-row">
          <div>
            <label>Column</label>
            <select value={f.column} onChange={(e) => setF({ ...f, column: e.target.value as any })}>
              {COLUMNS.map((c) => <option key={c.id} value={c.id}>{c.label}</option>)}
            </select>
          </div>
          <div>
            <label>Priority</label>
            <select value={f.priority} onChange={(e) => setF({ ...f, priority: e.target.value as any })}>
              <option value="high">High</option>
              <option value="medium">Medium</option>
              <option value="low">Low</option>
            </select>
          </div>
        </div>
        <div className="form-row">
          <div>
            <label>Assignee</label>
            <select value={f.assignee} onChange={(e) => setF({ ...f, assignee: e.target.value === "" ? "" : Number(e.target.value) })}>
              <option value="">Unassigned</option>
              {users.map((u) => <option key={u.id} value={u.id}>{u.name}</option>)}
            </select>
          </div>
          <div>
            <label>Pull request URL</label>
            <input value={f.pr_url} onChange={(e) => setF({ ...f, pr_url: e.target.value })} placeholder="https://…/pull/12" />
          </div>
        </div>

        <label>Reference images (for bug reports)</label>
        <div
          className="paste-zone"
          onClick={() => fileInput.current?.click()}
          onDrop={(e) => { e.preventDefault(); uploadFiles(Array.from(e.dataTransfer.files)); }}
          onDragOver={(e) => e.preventDefault()}
        >
          <input ref={fileInput} type="file" accept="image/*" multiple hidden
            onChange={(e) => uploadFiles(Array.from(e.target.files ?? []))} />
          {uploading ? "Uploading…" : <>Paste a screenshot (Ctrl/⌘+V), click to choose, or drop images here</>}
        </div>
        {note && <div className="paste-note">{note}</div>}
        {images.length > 0 && (
          <div className="img-grid">
            {images.map((img) => (
              <div key={img.id} className="img-thumb">
                <AuthImage path={api.cardImagePath(projectId, card.id, img.id)} alt={img.filename} />
                <button type="button" className="img-del" onClick={() => removeImage(img.id)}>×</button>
              </div>
            ))}
          </div>
        )}

        <div className="modal-actions">
          <button type="button" className="btn ghost" onClick={onClose}>Close</button>
          <button className="btn primary" disabled={busy}>{busy ? "Saving…" : "Save changes"}</button>
        </div>
      </form>
    </div>
  );
}
