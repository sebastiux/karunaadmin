export type Role = "admin" | "developer" | "client";

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
  order: number;
  created_at: string;
  latest_analysis: AIAnalysis | null;
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
