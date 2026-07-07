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
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


# --------------------------------------------------------------------------- #
# Enums
# --------------------------------------------------------------------------- #
class UserRole(str, enum.Enum):
    admin = "admin"
    developer = "developer"
    client = "client"


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
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.developer)
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
    order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    project: Mapped["Project"] = relationship(back_populates="deliverables")
    plan_point: Mapped["PlanPoint"] = relationship(back_populates="deliverables")
    analyses: Mapped[list["AIAnalysis"]] = relationship(
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
