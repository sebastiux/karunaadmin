import type {
  AIAnalysis,
  Deliverable,
  KanbanCard,
  KanbanColumnId,
  MonitoringOverview,
  Project,
  ProjectDetail,
  User,
} from "./types";

const BASE = import.meta.env.VITE_API_URL || "";

let token: string | null = localStorage.getItem("token");

export function setToken(t: string | null) {
  token = t;
  if (t) localStorage.setItem("token", t);
  else localStorage.removeItem("token");
}

export function getToken() {
  return token;
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${BASE}${path}`, { ...options, headers });
  if (res.status === 401) {
    setToken(null);
    throw new Error("Session expired. Please log in again.");
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || JSON.stringify(body);
    } catch {
      /* ignore */
    }
    throw new Error(typeof detail === "string" ? detail : "Request failed");
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const api = {
  // auth
  login: (email: string, password: string) =>
    request<{ access_token: string; user: User }>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  me: () => request<User>("/api/auth/me"),
  users: () => request<User[]>("/api/auth/users"),

  // projects
  projects: () => request<Project[]>("/api/projects"),
  project: (id: number) => request<ProjectDetail>(`/api/projects/${id}`),
  createProject: (name: string, description: string) =>
    request<Project>("/api/projects", {
      method: "POST",
      body: JSON.stringify({ name, description }),
    }),
  submitMasterPlan: (id: number, master_plan: string) =>
    request<ProjectDetail>(`/api/projects/${id}/master-plan`, {
      method: "POST",
      body: JSON.stringify({ master_plan, generate_deliverables: true }),
    }),
  deleteProject: (id: number) =>
    request<void>(`/api/projects/${id}`, { method: "DELETE" }),

  // deliverables
  deliverables: (projectId: number, clientOnly = false) =>
    request<Deliverable[]>(
      `/api/projects/${projectId}/deliverables${clientOnly ? "?client_only=true" : ""}`
    ),
  createDeliverable: (projectId: number, body: Partial<Deliverable>) =>
    request<Deliverable>(`/api/projects/${projectId}/deliverables`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  updateDeliverable: (
    projectId: number,
    id: number,
    body: Partial<Deliverable>
  ) =>
    request<Deliverable>(`/api/projects/${projectId}/deliverables/${id}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  deleteDeliverable: (projectId: number, id: number) =>
    request<void>(`/api/projects/${projectId}/deliverables/${id}`, {
      method: "DELETE",
    }),
  analyzeDeliverable: (projectId: number, id: number) =>
    request<AIAnalysis>(
      `/api/projects/${projectId}/deliverables/${id}/analyze`,
      { method: "POST" }
    ),
  analyses: (projectId: number, id: number) =>
    request<AIAnalysis[]>(
      `/api/projects/${projectId}/deliverables/${id}/analyses`
    ),

  // kanban
  cards: (projectId: number) =>
    request<KanbanCard[]>(`/api/projects/${projectId}/cards`),
  createCard: (projectId: number, body: Partial<KanbanCard>) =>
    request<KanbanCard>(`/api/projects/${projectId}/cards`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  updateCard: (projectId: number, id: number, body: Partial<KanbanCard>) =>
    request<KanbanCard>(`/api/projects/${projectId}/cards/${id}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  moveCard: (projectId: number, id: number, column: KanbanColumnId) =>
    request<KanbanCard>(`/api/projects/${projectId}/cards/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ column }),
    }),
  deleteCard: (projectId: number, id: number) =>
    request<void>(`/api/projects/${projectId}/cards/${id}`, {
      method: "DELETE",
    }),

  // monitoring
  monitoring: (projectId: number) =>
    request<MonitoringOverview>(`/api/projects/${projectId}/monitoring`),
};
