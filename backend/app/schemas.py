"""Pydantic request/response schemas."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr

from app.models import (
    DeliverableStatus,
    KanbanColumn,
    ProjectStatus,
    UserRole,
)


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)


# --------------------------- Auth --------------------------------------- #
class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserOut"


class UserCreate(BaseModel):
    email: EmailStr
    name: str
    password: str
    role: UserRole = UserRole.dev
    # For clients: the projects they should have access to.
    project_ids: list[int] = []


class UserOut(ORMModel):
    id: int
    email: EmailStr
    name: str
    role: UserRole
    created_at: datetime


# --------------------------- Projects ----------------------------------- #
class ProjectCreate(BaseModel):
    name: str
    description: str = ""


class MasterPlanSubmit(BaseModel):
    master_plan: str
    generate_deliverables: bool = True


class PlanPointOut(ORMModel):
    id: int
    title: str
    description: str
    order: int


class ProjectOut(ORMModel):
    id: int
    name: str
    description: str
    status: ProjectStatus
    created_at: datetime
    updated_at: datetime


class ProjectDetail(ProjectOut):
    master_plan: str
    plan_points: list[PlanPointOut] = []


# --------------------------- Deliverables ------------------------------- #
class DeliverableCreate(BaseModel):
    title: str
    description: str = ""
    acceptance_criteria: str = ""
    plan_point_id: int | None = None
    client_visible: bool = True
    assignee_id: int | None = None


class DeliverableUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    acceptance_criteria: str | None = None
    status: DeliverableStatus | None = None
    plan_point_id: int | None = None
    client_visible: bool | None = None
    assignee_id: int | None = None
    completed: bool | None = None


class DeliverableFileOut(ORMModel):
    id: int
    deliverable_id: int
    filename: str
    content_type: str
    size: int
    uploaded_by: int | None
    created_at: datetime


class AIAnalysisOut(ORMModel):
    id: int
    deliverable_id: int
    score: float
    summary: str
    strengths: str
    gaps: str
    recommendations: str
    model: str
    is_mock: int
    created_at: datetime


class DeliverableOut(ORMModel):
    id: int
    project_id: int
    plan_point_id: int | None
    title: str
    description: str
    acceptance_criteria: str
    status: DeliverableStatus
    ai_generated: int
    client_visible: int
    completed: int
    assignee_id: int | None
    assignee_name: str | None = None
    order: int
    created_at: datetime
    file_count: int = 0
    # AI analysis is INTERNAL ONLY — never populated for client viewers.
    latest_analysis: AIAnalysisOut | None = None


# --------------------------- Kanban ------------------------------------- #
class KanbanCardCreate(BaseModel):
    title: str
    description: str = ""
    column: KanbanColumn = KanbanColumn.backlog
    assignee_id: int | None = None
    pr_url: str = ""
    priority: str = "medium"


class KanbanCardUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    column: KanbanColumn | None = None
    assignee_id: int | None = None
    pr_url: str | None = None
    priority: str | None = None
    order: int | None = None


class KanbanCardOut(ORMModel):
    id: int
    project_id: int
    title: str
    description: str
    column: KanbanColumn
    assignee_id: int | None
    assignee_name: str | None = None
    pr_url: str
    priority: str
    order: int
    created_at: datetime
    updated_at: datetime


# --------------------------- Monitoring --------------------------------- #
class PlanPointProgress(BaseModel):
    plan_point_id: int
    title: str
    description: str
    total_deliverables: int
    completed_deliverables: int
    progress: float                # 0..100
    avg_ai_score: float | None     # average alignment score, if analyzed


class MonitoringOverview(BaseModel):
    project_id: int
    project_name: str
    status: ProjectStatus
    overall_progress: float
    total_deliverables: int
    completed_deliverables: int
    avg_ai_score: float | None
    points: list[PlanPointProgress]


# --------------------------- Files -------------------------------------- #
class ProjectFileOut(ORMModel):
    id: int
    project_id: int
    filename: str
    content_type: str
    size: int
    extracted_chars: int = 0
    created_at: datetime


class FileUploadResult(BaseModel):
    file: ProjectFileOut
    extracted_text: str  # returned so the client can prefill the plan editor


# --------------------------- Document requests -------------------------- #
class DocRequestCreate(BaseModel):
    title: str
    description: str = ""
    recipient_user_ids: list[int] = []


class DocRequestFileOut(ORMModel):
    id: int
    request_id: int
    filename: str
    content_type: str
    size: int
    uploaded_by: int | None
    created_at: datetime


class DocRequestOut(BaseModel):
    id: int
    project_id: int
    title: str
    description: str
    status: str
    created_by: int | None
    created_by_name: str | None = None
    created_at: datetime
    recipient_ids: list[int] = []
    recipient_names: list[str] = []
    files: list[DocRequestFileOut] = []


# --------------------------- Commercial --------------------------------- #
class CommercialBoardCreate(BaseModel):
    name: str
    description: str = ""


class CommercialBoardOut(ORMModel):
    id: int
    name: str
    description: str
    created_at: datetime


class CommercialCardCreate(BaseModel):
    title: str
    description: str = ""
    company: str = ""
    contact: str = ""
    estimated_value: float = 0.0
    column: str = "lead"
    assignee_id: int | None = None
    priority: str = "medium"


class CommercialCardUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    company: str | None = None
    contact: str | None = None
    estimated_value: float | None = None
    column: str | None = None
    assignee_id: int | None = None
    priority: str | None = None
    order: int | None = None


class CommercialCardOut(ORMModel):
    id: int
    board_id: int
    title: str
    description: str
    company: str
    contact: str
    estimated_value: float
    column: str
    assignee_id: int | None
    assignee_name: str | None = None
    priority: str
    order: int
    created_at: datetime
    updated_at: datetime


# --------------------------- Tickets (cross-project) -------------------- #
class TicketOut(BaseModel):
    id: int
    project_id: int
    project_name: str
    title: str
    description: str
    column: KanbanColumn
    assignee_id: int | None
    assignee_name: str | None
    pr_url: str
    priority: str
    updated_at: datetime


TokenResponse.model_rebuild()
