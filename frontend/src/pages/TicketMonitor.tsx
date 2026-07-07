import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import type { KanbanColumnId, Ticket } from "../types";

const COLUMNS: { id: KanbanColumnId; label: string }[] = [
  { id: "backlog", label: "Backlog" },
  { id: "todo", label: "To do" },
  { id: "in_progress", label: "In progress" },
  { id: "in_review", label: "In review" },
  { id: "done", label: "Done" },
];

export default function TicketMonitor() {
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [loading, setLoading] = useState(true);
  const [projectFilter, setProjectFilter] = useState<number | "all">("all");

  useEffect(() => {
    api.tickets().then(setTickets).finally(() => setLoading(false));
  }, []);

  const projects = useMemo(() => {
    const m = new Map<number, string>();
    tickets.forEach((t) => m.set(t.project_id, t.project_name));
    return [...m.entries()];
  }, [tickets]);

  const visible = useMemo(
    () =>
      projectFilter === "all"
        ? tickets
        : tickets.filter((t) => t.project_id === projectFilter),
    [tickets, projectFilter]
  );

  const byColumn = useMemo(() => {
    const map: Record<string, Ticket[]> = {};
    for (const col of COLUMNS) map[col.id] = [];
    for (const t of visible) (map[t.column] ??= []).push(t);
    return map;
  }, [visible]);

  if (loading) return <div className="container"><div className="spinner" /></div>;

  return (
    <div className="container">
      <div className="page-head">
        <div>
          <h1>Ticket Monitor</h1>
          <p className="muted">
            Every code-review ticket across all projects, in one board.
          </p>
        </div>
        <select
          className="status-select"
          value={projectFilter}
          onChange={(e) =>
            setProjectFilter(e.target.value === "all" ? "all" : Number(e.target.value))
          }
        >
          <option value="all">All projects ({tickets.length})</option>
          {projects.map(([id, name]) => (
            <option key={id} value={id}>{name}</option>
          ))}
        </select>
      </div>

      {tickets.length === 0 ? (
        <div className="info-box">
          No tickets yet. Add cards in any project's <strong>Code Review</strong> board.
        </div>
      ) : (
        <div className="board">
          {COLUMNS.map((col) => (
            <div key={col.id} className="board-col">
              <div className="board-col-head">
                <span>{col.label}</span>
                <span className="count">{byColumn[col.id].length}</span>
              </div>
              <div className="board-col-body">
                {byColumn[col.id].map((t) => (
                  <div key={t.id} className="kcard">
                    <div className="kcard-top">
                      <span className="ticket-no">{t.ticket_number}</span>
                      <span className={`prio prio-${t.priority}`}>{t.priority}</span>
                    </div>
                    <div className="kcard-title">{t.title}</div>
                    <Link to={`/projects/${t.project_id}`} className="ticket-project">
                      {t.project_name}
                    </Link>
                    <div className="kcard-foot">
                      {t.assignee_name && <span className="assignee">{t.assignee_name}</span>}
                      {t.pr_url && (
                        <a href={t.pr_url} target="_blank" rel="noreferrer" className="pr-link">
                          PR ↗
                        </a>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
