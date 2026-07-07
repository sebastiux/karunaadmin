"""Client-facing visual monitoring — non-technical progress view.

Progress is *derived* from deliverable statuses grouped by master-plan point,
plus the average AI alignment score where analyses exist.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.access import require_project_access
from app.auth import get_current_user
from app.database import get_db
from app.models import (
    AIAnalysis,
    Deliverable,
    DeliverableStatus,
    PlanPoint,
    Project,
    User,
)
from app.schemas import (
    MonitoringOverview,
    PlanPointProgress,
)

router = APIRouter(prefix="/api/projects/{project_id}/monitoring", tags=["monitoring"])

_DONE_STATES = {DeliverableStatus.approved, DeliverableStatus.submitted}


def _avg(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 1) if values else None


def _is_done(d: Deliverable) -> bool:
    # A deliverable counts as complete if explicitly marked completed, or if its
    # workflow status is approved/submitted.
    return bool(d.completed) or DeliverableStatus(d.status) in _DONE_STATES


@router.get("", response_model=MonitoringOverview)
def project_monitoring(
    project_id: int,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    require_project_access(db, current, project_id)

    points = (
        db.query(PlanPoint)
        .filter(PlanPoint.project_id == project_id)
        .order_by(PlanPoint.order)
        .all()
    )
    # Only client-visible deliverables count toward the client view.
    deliverables = (
        db.query(Deliverable)
        .filter(
            Deliverable.project_id == project_id,
            Deliverable.client_visible == 1,
        )
        .all()
    )

    # Latest AI score per deliverable (if any).
    latest_scores: dict[int, float] = {}
    analyses = (
        db.query(AIAnalysis)
        .join(Deliverable, AIAnalysis.deliverable_id == Deliverable.id)
        .filter(Deliverable.project_id == project_id)
        .order_by(AIAnalysis.created_at.asc())
        .all()
    )
    for a in analyses:  # ascending order => last write wins = latest score
        latest_scores[a.deliverable_id] = a.score

    by_point: dict[int | None, list[Deliverable]] = {}
    for d in deliverables:
        by_point.setdefault(d.plan_point_id, []).append(d)

    point_progress: list[PlanPointProgress] = []
    all_scores: list[float] = []
    total_all = completed_all = 0

    for p in points:
        group = by_point.get(p.id, [])
        total = len(group)
        completed = sum(1 for d in group if _is_done(d))
        scores = [latest_scores[d.id] for d in group if d.id in latest_scores]
        all_scores.extend(scores)
        total_all += total
        completed_all += completed
        point_progress.append(
            PlanPointProgress(
                plan_point_id=p.id,
                title=p.title,
                description=p.description,
                total_deliverables=total,
                completed_deliverables=completed,
                progress=round(100 * completed / total, 1) if total else 0.0,
                avg_ai_score=_avg(scores),
            )
        )

    # Deliverables not linked to any plan point (manually added / unassigned).
    orphan = by_point.get(None, [])
    if orphan:
        total = len(orphan)
        completed = sum(1 for d in orphan if _is_done(d))
        scores = [latest_scores[d.id] for d in orphan if d.id in latest_scores]
        all_scores.extend(scores)
        total_all += total
        completed_all += completed
        point_progress.append(
            PlanPointProgress(
                plan_point_id=0,
                title="Other deliverables",
                description="Deliverables not tied to a specific plan point.",
                total_deliverables=total,
                completed_deliverables=completed,
                progress=round(100 * completed / total, 1) if total else 0.0,
                avg_ai_score=_avg(scores),
            )
        )

    overall = round(100 * completed_all / total_all, 1) if total_all else 0.0

    return MonitoringOverview(
        project_id=project.id,
        project_name=project.name,
        status=project.status,
        overall_progress=overall,
        total_deliverables=total_all,
        completed_deliverables=completed_all,
        avg_ai_score=_avg(all_scores),
        points=point_progress,
    )
