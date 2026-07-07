import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api";
import type { KanbanCard, KanbanColumnId, User } from "../types";

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
                    <span className={`prio prio-${card.priority}`}>{card.priority}</span>
                    <button className="kcard-del" onClick={() => remove(card.id)} title="Delete">
                      ×
                    </button>
                  </div>
                  <div className="kcard-title">{card.title}</div>
                  {card.description && <div className="kcard-desc">{card.description}</div>}
                  <div className="kcard-foot">
                    {card.assignee_name && <span className="assignee">{card.assignee_name}</span>}
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
