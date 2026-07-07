import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { useAuth } from "../auth";
import { isCommercialAdmin } from "../types";
import type { CommercialBoard, CommercialCard, CommercialColumnId, User } from "../types";

const COLUMNS: { id: CommercialColumnId; label: string }[] = [
  { id: "lead", label: "Lead" },
  { id: "contacted", label: "Contacted" },
  { id: "qualified", label: "Qualified" },
  { id: "proposal", label: "Proposal" },
  { id: "won", label: "Won" },
  { id: "lost", label: "Lost" },
];

const PRIO = { high: 0, medium: 1, low: 2 } as const;

export default function Commercial() {
  const { user } = useAuth();
  const canManageBoards = isCommercialAdmin(user?.role);
  const [boards, setBoards] = useState<CommercialBoard[]>([]);
  const [boardId, setBoardId] = useState<number | null>(null);
  const [cards, setCards] = useState<CommercialCard[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [dragId, setDragId] = useState<number | null>(null);
  const [overCol, setOverCol] = useState<CommercialColumnId | null>(null);
  const [composeCol, setComposeCol] = useState<CommercialColumnId | null>(null);
  const [newBoard, setNewBoard] = useState(false);

  useEffect(() => {
    api.commercialBoards().then((b) => {
      setBoards(b);
      if (b.length) setBoardId((id) => id ?? b[0].id);
    });
    api.users().then(setUsers).catch(() => setUsers([]));
  }, []);

  useEffect(() => {
    if (boardId != null) api.commercialCards(boardId).then(setCards);
  }, [boardId]);

  const byColumn = useMemo(() => {
    const map: Record<string, CommercialCard[]> = {};
    for (const c of COLUMNS) map[c.id] = [];
    for (const card of cards) (map[card.column] ??= []).push(card);
    for (const k of Object.keys(map))
      map[k].sort((a, b) => PRIO[a.priority] - PRIO[b.priority] || a.order - b.order);
    return map;
  }, [cards]);

  const pipelineValue = useMemo(
    () =>
      cards
        .filter((c) => c.column !== "lost")
        .reduce((s, c) => s + (c.estimated_value || 0), 0),
    [cards]
  );

  async function drop(col: CommercialColumnId) {
    setOverCol(null);
    if (dragId == null) return;
    const card = cards.find((c) => c.id === dragId);
    setDragId(null);
    if (!card || card.column === col) return;
    setCards((cs) => cs.map((c) => (c.id === card.id ? { ...c, column: col } : c)));
    await api.updateCommercialCard(card.id, { column: col });
  }

  async function remove(id: number) {
    setCards((cs) => cs.filter((c) => c.id !== id));
    await api.deleteCommercialCard(id);
  }

  return (
    <div className="container">
      <div className="page-head">
        <div>
          <h1>Commercial</h1>
          <p className="muted">Source, qualify and win new IT project opportunities.</p>
        </div>
        <div className="head-controls">
          {boards.length > 0 && (
            <select
              className="status-select"
              value={boardId ?? ""}
              onChange={(e) => setBoardId(Number(e.target.value))}
            >
              {boards.map((b) => (
                <option key={b.id} value={b.id}>{b.name}</option>
              ))}
            </select>
          )}
          {canManageBoards && (
            <button className="btn ghost" onClick={() => setNewBoard(true)}>
              + Board
            </button>
          )}
        </div>
      </div>

      {boardId == null ? (
        <div className="info-box">No commercial boards yet.</div>
      ) : (
        <>
          <div className="pipeline-summary">
            <span className="pipe-num">
              ${pipelineValue.toLocaleString()}
            </span>
            <span className="muted">open pipeline value · {cards.length} opportunities</span>
          </div>
          <div className="board board-6">
            {COLUMNS.map((col) => (
              <div
                key={col.id}
                className={`board-col ${overCol === col.id ? "drop-over" : ""} col-${col.id}`}
                onDragOver={(e) => { e.preventDefault(); setOverCol(col.id); }}
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
                        <button className="kcard-del" onClick={() => remove(card.id)}>×</button>
                      </div>
                      <div className="kcard-title">{card.title}</div>
                      {card.company && <div className="kcard-company">{card.company}</div>}
                      {card.estimated_value > 0 && (
                        <div className="kcard-value">${card.estimated_value.toLocaleString()}</div>
                      )}
                      <div className="kcard-foot">
                        {card.assignee_name && <span className="assignee">{card.assignee_name}</span>}
                      </div>
                    </div>
                  ))}
                  <button className="add-in-col" onClick={() => setComposeCol(col.id)}>+ Add</button>
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      {composeCol && boardId != null && (
        <CardComposer
          boardId={boardId}
          column={composeCol}
          users={users}
          onClose={() => setComposeCol(null)}
          onCreated={(c) => setCards((cs) => [...cs, c])}
        />
      )}

      {newBoard && (
        <BoardComposer
          onClose={() => setNewBoard(false)}
          onCreated={(b) => {
            setBoards((bs) => [...bs, b]);
            setBoardId(b.id);
          }}
        />
      )}
    </div>
  );
}

function CardComposer({
  boardId, column, users, onClose, onCreated,
}: {
  boardId: number;
  column: CommercialColumnId;
  users: User[];
  onClose: () => void;
  onCreated: (c: CommercialCard) => void;
}) {
  const [f, setF] = useState({
    title: "", company: "", contact: "", estimated_value: "", priority: "medium" as const,
    assignee: "" as number | "",
  });
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      const c = await api.createCommercialCard(boardId, {
        title: f.title,
        company: f.company,
        contact: f.contact,
        estimated_value: Number(f.estimated_value) || 0,
        priority: f.priority,
        column,
        assignee_id: f.assignee === "" ? null : Number(f.assignee),
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
        <h2>New opportunity · {column}</h2>
        <label>Title</label>
        <input value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} autoFocus required />
        <div className="form-row">
          <div>
            <label>Company</label>
            <input value={f.company} onChange={(e) => setF({ ...f, company: e.target.value })} />
          </div>
          <div>
            <label>Contact</label>
            <input value={f.contact} onChange={(e) => setF({ ...f, contact: e.target.value })} />
          </div>
        </div>
        <div className="form-row">
          <div>
            <label>Estimated value (USD)</label>
            <input type="number" value={f.estimated_value} onChange={(e) => setF({ ...f, estimated_value: e.target.value })} />
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
        <label>Assignee</label>
        <select value={f.assignee} onChange={(e) => setF({ ...f, assignee: e.target.value === "" ? "" : Number(e.target.value) })}>
          <option value="">Unassigned</option>
          {users.map((u) => <option key={u.id} value={u.id}>{u.name}</option>)}
        </select>
        <div className="modal-actions">
          <button type="button" className="btn ghost" onClick={onClose}>Cancel</button>
          <button className="btn primary" disabled={busy}>{busy ? "Adding…" : "Add"}</button>
        </div>
      </form>
    </div>
  );
}

function BoardComposer({
  onClose, onCreated,
}: {
  onClose: () => void;
  onCreated: (b: CommercialBoard) => void;
}) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      onCreated(await api.createCommercialBoard(name, description));
      onClose();
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <form className="modal" onClick={(e) => e.stopPropagation()} onSubmit={submit}>
        <h2>New commercial board</h2>
        <label>Name</label>
        <input value={name} onChange={(e) => setName(e.target.value)} autoFocus required />
        <label>Description</label>
        <textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={3} />
        <div className="modal-actions">
          <button type="button" className="btn ghost" onClick={onClose}>Cancel</button>
          <button className="btn primary" disabled={busy}>{busy ? "Creating…" : "Create"}</button>
        </div>
      </form>
    </div>
  );
}
