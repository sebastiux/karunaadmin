export type Role =
  | "admin"
  | "admin_dev"
  | "admin_comercial"
  | "dev"
  | "comercial"
  | "client";

export const ROLE_LABELS: Record<Role, string> = {
  admin: "Super admin",
  admin_dev: "Admin · Dev",
  admin_comercial: "Admin · Commercial",
  dev: "Dev team",
  comercial: "Commercial team",
  client: "Client",
};

// ---- role capability helpers (mirror backend permissions.py) ----
export const isSuper = (r?: Role) => r === "admin";
export const isDevAdmin = (r?: Role) => r === "admin" || r === "admin_dev";
export const isCommercialAdmin = (r?: Role) =>
  r === "admin" || r === "admin_comercial";
export const isAnyAdmin = (r?: Role) =>
  r === "admin" || r === "admin_dev" || r === "admin_comercial";
export const isDevTeam = (r?: Role) =>
  r === "admin" || r === "admin_dev" || r === "dev";
export const isCommercialTeam = (r?: Role) =>
  r === "admin" || r === "admin_comercial" || r === "comercial";

export interface User {
  id: number;
  email: string;
  name: string;
  role: Role;
  created_at: string;
}

export type ProjectStatus = "draft" | "active" | "completed" | "archived";

export interface Project {
  id: number;
  name: string;
  description: string;
  status: ProjectStatus;
  created_at: string;
  updated_at: string;
}

export interface PlanPoint {
  id: number;
  title: string;
  description: string;
  order: number;
}

export interface ProjectDetail extends Project {
  master_plan: string;
  plan_points: PlanPoint[];
}

export type DeliverableStatus =
  | "pending"
  | "in_progress"
  | "submitted"
  | "approved"
  | "rejected";

export interface AIAnalysis {
  id: number;
  deliverable_id: number;
  score: number;
  summary: string;
  strengths: string;
  gaps: string;
  recommendations: string;
  model: string;
  is_mock: number;
  created_at: string;
}

export interface Deliverable {
  id: number;
  project_id: number;
  plan_point_id: number | null;
  title: string;
  description: string;
  acceptance_criteria: string;
  status: DeliverableStatus;
  ai_generated: number;
  client_visible: number;
  completed: number;
  assignee_id: number | null;
  assignee_name: string | null;
  order: number;
  created_at: string;
  file_count: number;
  latest_analysis: AIAnalysis | null; // internal viewers only
}

export interface DeliverableFile {
  id: number;
  deliverable_id: number;
  filename: string;
  content_type: string;
  size: number;
  uploaded_by: number | null;
  created_at: string;
}

export type KanbanColumnId =
  | "backlog"
  | "todo"
  | "in_progress"
  | "in_review"
  | "done";

export interface KanbanCard {
  id: number;
  project_id: number;
  title: string;
  description: string;
  column: KanbanColumnId;
  assignee_id: number | null;
  assignee_name: string | null;
  pr_url: string;
  priority: "low" | "medium" | "high";
  order: number;
  created_at: string;
  updated_at: string;
}

export interface PlanPointProgress {
  plan_point_id: number;
  title: string;
  description: string;
  total_deliverables: number;
  completed_deliverables: number;
  progress: number;
  avg_ai_score: number | null;
}

export interface MonitoringOverview {
  project_id: number;
  project_name: string;
  status: ProjectStatus;
  overall_progress: number;
  total_deliverables: number;
  completed_deliverables: number;
  avg_ai_score: number | null;
  points: PlanPointProgress[];
}

export interface ProjectFile {
  id: number;
  project_id: number;
  filename: string;
  content_type: string;
  size: number;
  extracted_chars: number;
  created_at: string;
}

export type CommercialColumnId =
  | "lead"
  | "contacted"
  | "qualified"
  | "proposal"
  | "won"
  | "lost";

export interface CommercialBoard {
  id: number;
  name: string;
  description: string;
  created_at: string;
}

export interface CommercialCard {
  id: number;
  board_id: number;
  title: string;
  description: string;
  company: string;
  contact: string;
  estimated_value: number;
  column: CommercialColumnId;
  assignee_id: number | null;
  assignee_name: string | null;
  priority: "low" | "medium" | "high";
  order: number;
  created_at: string;
  updated_at: string;
}

export interface Ticket {
  id: number;
  project_id: number;
  project_name: string;
  title: string;
  description: string;
  column: KanbanColumnId;
  assignee_id: number | null;
  assignee_name: string | null;
  pr_url: string;
  priority: "low" | "medium" | "high";
  updated_at: string;
}
