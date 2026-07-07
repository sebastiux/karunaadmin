"""Database models.

Domain overview
---------------
A **Project** is configured by submitting a **master plan**. The master plan is
broken into **PlanPoint** rows (the milestones/objectives the client cares
about). From those points the AI generates **Deliverable** rows. Each
deliverable can be analyzed by Grok, producing an **AIAnalysis** scoring it
against the plan.

The **code review** panel is fully separate and AI-free: a Kanban board of
**KanbanCard** rows grouped into fixed columns, worked by several developers.

Client monitoring is a *view* derived from PlanPoint + Deliverable progress —
no dedicated table needed.
"""
from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.mysql import LONGBLOB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

# MySQL BLOB caps at 64 KB; use LONGBLOB there (up to 4 GB) for file storage.
# On SQLite (dev) LargeBinary is unbounded, so the variant is a no-op.
FileBlob = LargeBinary().with_variant(LONGBLOB(), "mysql")


# --------------------------------------------------------------------------- #
# Enums
# --------------------------------------------------------------------------- #
class UserRole(str, enum.Enum):
    admin = "admin"                      # super admin — full access everywhere
    admin_dev = "admin_dev"              # full access, dev-focused
    admin_comercial = "admin_comercial"  # manages the commercial team & boards
    dev = "dev"                          # dev team member
    comercial = "comercial"              # commercial team member
    client = "client"                    # read-only client monitoring


class ProjectStatus(str, enum.Enum):
    draft = "draft"          # created, master plan not yet processed
    active = "active"        # deliverables generated, work in progress
    completed = "completed"
    archived = "archived"


class DeliverableStatus(str, enum.Enum):
    pending = "pending"
    in_progress = "in_progress"
    submitted = "submitted"
    approved = "approved"
    rejected = "rejected"


class KanbanColumn(str, enum.Enum):
    backlog = "backlog"
    todo = "todo"
    in_progress = "in_progress"
    in_review = "in_review"
    done = "done"


# --------------------------------------------------------------------------- #
# Models
# --------------------------------------------------------------------------- #
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    password_hash: Mapped[str] = mapped_column(String(255))
    # Stored as a plain string (not a DB ENUM) so new roles can be added without
    # a schema migration. Values come from UserRole.
    role: Mapped[str] = mapped_column(String(32), default=UserRole.dev.value)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[ProjectStatus] = mapped_column(
        Enum(ProjectStatus), default=ProjectStatus.draft
    )
    master_plan: Mapped[str] = mapped_column(Text, default="")  # raw submitted plan
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    plan_points: Mapped[list["PlanPoint"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    deliverables: Mapped[list["Deliverable"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    cards: Mapped[list["KanbanCard"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )


class ProjectMember(Base):
    """Grants a user (typically a client) access to a specific project.

    Internal users (dev team) can access every project; clients can only access
    projects they're a member of.
    """

    __tablename__ = "project_members"
    __table_args__ = (UniqueConstraint("project_id", "user_id", name="uq_project_user"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class PlanPoint(Base):
    """A single objective/milestone extracted from the master plan."""

    __tablename__ = "plan_points"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[str] = mapped_column(Text, default="")
    order: Mapped[int] = mapped_column(Integer, default=0)

    project: Mapped["Project"] = relationship(back_populates="plan_points")
    deliverables: Mapped[list["Deliverable"]] = relationship(
        back_populates="plan_point"
    )


class Deliverable(Base):
    __tablename__ = "deliverables"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    plan_point_id: Mapped[int | None] = mapped_column(
        ForeignKey("plan_points.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[str] = mapped_column(Text, default="")
    acceptance_criteria: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[DeliverableStatus] = mapped_column(
        Enum(DeliverableStatus), default=DeliverableStatus.pending
    )
    ai_generated: Mapped[int] = mapped_column(Integer, default=0)  # 0/1 flag
    client_visible: Mapped[int] = mapped_column(Integer, default=1)
    completed: Mapped[int] = mapped_column(Integer, default=0)  # 0/1 "done" flag
    # A deliverable may be assigned to any user, including a client who must
    # submit its documentation.
    assignee_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    project: Mapped["Project"] = relationship(back_populates="deliverables")
    plan_point: Mapped["PlanPoint"] = relationship(back_populates="deliverables")
    assignee: Mapped["User"] = relationship()
    analyses: Mapped[list["AIAnalysis"]] = relationship(
        back_populates="deliverable", cascade="all, delete-orphan"
    )
    files: Mapped[list["DeliverableFile"]] = relationship(
        back_populates="deliverable", cascade="all, delete-orphan"
    )


class AIAnalysis(Base):
    """A Grok analysis of a deliverable measured against the master plan."""

    __tablename__ = "ai_analyses"

    id: Mapped[int] = mapped_column(primary_key=True)
    deliverable_id: Mapped[int] = mapped_column(
        ForeignKey("deliverables.id", ondelete="CASCADE")
    )
    score: Mapped[float] = mapped_column(Float, default=0.0)  # 0..100 alignment
    summary: Mapped[str] = mapped_column(Text, default="")
    strengths: Mapped[str] = mapped_column(Text, default="")        # newline list
    gaps: Mapped[str] = mapped_column(Text, default="")             # newline list
    recommendations: Mapped[str] = mapped_column(Text, default="")  # newline list
    model: Mapped[str] = mapped_column(String(100), default="")
    is_mock: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    deliverable: Mapped["Deliverable"] = relationship(back_populates="analyses")


class KanbanCard(Base):
    """A code-review / follow-up card. AI-free by design."""

    __tablename__ = "kanban_cards"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    ticket_number: Mapped[str] = mapped_column(String(32), default="")  # e.g. TKT-0012
    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[str] = mapped_column(Text, default="")
    column: Mapped[KanbanColumn] = mapped_column(
        Enum(KanbanColumn), default=KanbanColumn.backlog
    )
    assignee_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    pr_url: Mapped[str] = mapped_column(String(1000), default="")
    priority: Mapped[str] = mapped_column(String(20), default="medium")  # low/med/high
    order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    project: Mapped["Project"] = relationship(back_populates="cards")
    assignee: Mapped["User"] = relationship()
    images: Mapped[list["KanbanCardImage"]] = relationship(
        back_populates="card", cascade="all, delete-orphan"
    )


class KanbanCardImage(Base):
    """A reference image (e.g. a bug screenshot) attached to a Kanban card."""

    __tablename__ = "kanban_card_images"

    id: Mapped[int] = mapped_column(primary_key=True)
    card_id: Mapped[int] = mapped_column(ForeignKey("kanban_cards.id", ondelete="CASCADE"))
    filename: Mapped[str] = mapped_column(String(500), default="image.png")
    content_type: Mapped[str] = mapped_column(String(200), default="image/png")
    size: Mapped[int] = mapped_column(Integer, default=0)
    data: Mapped[bytes] = mapped_column(FileBlob)
    uploaded_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    card: Mapped["KanbanCard"] = relationship(back_populates="images")


class ProjectFile(Base):
    """An uploaded document attached to a project (master-plan source, specs…).

    Stored in the DB so files survive Railway's ephemeral filesystem. Text is
    extracted from PDF/DOCX/TXT/MD on upload so it can feed the AI generator.
    """

    __tablename__ = "project_files"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    filename: Mapped[str] = mapped_column(String(500))
    content_type: Mapped[str] = mapped_column(String(200), default="")
    size: Mapped[int] = mapped_column(Integer, default=0)
    data: Mapped[bytes] = mapped_column(FileBlob)          # raw file bytes
    extracted_text: Mapped[str] = mapped_column(Text, default="")
    uploaded_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class DeliverableFile(Base):
    """A document attached to a deliverable — e.g. documentation a client (or a
    developer) submits as the deliverable's evidence of completion."""

    __tablename__ = "deliverable_files"

    id: Mapped[int] = mapped_column(primary_key=True)
    deliverable_id: Mapped[int] = mapped_column(
        ForeignKey("deliverables.id", ondelete="CASCADE")
    )
    filename: Mapped[str] = mapped_column(String(500))
    content_type: Mapped[str] = mapped_column(String(200), default="")
    size: Mapped[int] = mapped_column(Integer, default=0)
    data: Mapped[bytes] = mapped_column(FileBlob)
    uploaded_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    deliverable: Mapped["Deliverable"] = relationship(back_populates="files")


class DocRequestStatus(str, enum.Enum):
    open = "open"            # awaiting client upload
    submitted = "submitted"  # client uploaded document(s)
    fulfilled = "fulfilled"  # accepted by the internal team


class DocumentRequest(Base):
    """A request from the internal team asking specific client users to upload
    documentation for a project."""

    __tablename__ = "document_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default=DocRequestStatus.open.value)
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    recipients: Mapped[list["DocumentRequestRecipient"]] = relationship(
        back_populates="request", cascade="all, delete-orphan"
    )
    files: Mapped[list["DocumentRequestFile"]] = relationship(
        back_populates="request", cascade="all, delete-orphan"
    )


class DocumentRequestRecipient(Base):
    __tablename__ = "document_request_recipients"
    __table_args__ = (
        UniqueConstraint("request_id", "user_id", name="uq_docreq_user"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(
        ForeignKey("document_requests.id", ondelete="CASCADE")
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))

    request: Mapped["DocumentRequest"] = relationship(back_populates="recipients")


class DocumentRequestFile(Base):
    __tablename__ = "document_request_files"

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(
        ForeignKey("document_requests.id", ondelete="CASCADE")
    )
    filename: Mapped[str] = mapped_column(String(500))
    content_type: Mapped[str] = mapped_column(String(200), default="")
    size: Mapped[int] = mapped_column(Integer, default=0)
    data: Mapped[bytes] = mapped_column(FileBlob)
    uploaded_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    request: Mapped["DocumentRequest"] = relationship(back_populates="files")


# --------------------------------------------------------------------------- #
# Commercial workspace — AI-free boards for sourcing NEW IT projects.
# Global (not tied to a delivery Project); worked by the commercial team.
# --------------------------------------------------------------------------- #
class CommercialColumn(str, enum.Enum):
    lead = "lead"
    contacted = "contacted"
    qualified = "qualified"
    proposal = "proposal"
    won = "won"
    lost = "lost"


class CommercialBoard(Base):
    __tablename__ = "commercial_boards"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    cards: Mapped[list["CommercialCard"]] = relationship(
        back_populates="board", cascade="all, delete-orphan"
    )


class CommercialCard(Base):
    __tablename__ = "commercial_cards"

    id: Mapped[int] = mapped_column(primary_key=True)
    board_id: Mapped[int] = mapped_column(
        ForeignKey("commercial_boards.id", ondelete="CASCADE")
    )
    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[str] = mapped_column(Text, default="")
    company: Mapped[str] = mapped_column(String(255), default="")
    contact: Mapped[str] = mapped_column(String(255), default="")
    estimated_value: Mapped[float] = mapped_column(Float, default=0.0)
    column: Mapped[str] = mapped_column(String(32), default=CommercialColumn.lead.value)
    assignee_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    priority: Mapped[str] = mapped_column(String(20), default="medium")
    order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    board: Mapped["CommercialBoard"] = relationship(back_populates="cards")
    assignee: Mapped["User"] = relationship()
