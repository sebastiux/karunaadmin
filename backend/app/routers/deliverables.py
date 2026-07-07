"""Deliverables panel + AI-analysis subpanel (Grok)."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_roles
from app.database import get_db
from app.permissions import DEV_ADMINS
from app.models import (
    AIAnalysis,
    Deliverable,
    Project,
    User,
    UserRole,
)
from app.schemas import (
    AIAnalysisOut,
    DeliverableCreate,
    DeliverableOut,
    DeliverableUpdate,
)
from app.services.grok import grok

router = APIRouter(prefix="/api/projects/{project_id}/deliverables", tags=["deliverables"])


def _latest_analysis(db: Session, deliverable_id: int) -> AIAnalysis | None:
    return (
        db.query(AIAnalysis)
        .filter(AIAnalysis.deliverable_id == deliverable_id)
        .order_by(AIAnalysis.created_at.desc(), AIAnalysis.id.desc())
        .first()
    )


def _to_out(db: Session, d: Deliverable) -> DeliverableOut:
    out = DeliverableOut.model_validate(d)
    latest = _latest_analysis(db, d.id)
    if latest:
        out.latest_analysis = AIAnalysisOut.model_validate(latest)
    return out


def _get_project_or_404(db: Session, project_id: int) -> Project:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.get("", response_model=list[DeliverableOut])
def list_deliverables(
    project_id: int,
    client_only: bool = False,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _get_project_or_404(db, project_id)
    q = db.query(Deliverable).filter(Deliverable.project_id == project_id)
    if client_only:
        q = q.filter(Deliverable.client_visible == 1)
    items = q.order_by(Deliverable.plan_point_id, Deliverable.order, Deliverable.id).all()
    return [_to_out(db, d) for d in items]


@router.post("", response_model=DeliverableOut, status_code=201)
def create_deliverable(
    project_id: int,
    payload: DeliverableCreate,
    _: User = Depends(require_roles(DEV_ADMINS)),
    db: Session = Depends(get_db),
):
    _get_project_or_404(db, project_id)
    d = Deliverable(
        project_id=project_id,
        plan_point_id=payload.plan_point_id,
        title=payload.title,
        description=payload.description,
        acceptance_criteria=payload.acceptance_criteria,
        client_visible=1 if payload.client_visible else 0,
        ai_generated=0,
    )
    db.add(d)
    db.commit()
    db.refresh(d)
    return _to_out(db, d)


@router.patch("/{deliverable_id}", response_model=DeliverableOut)
def update_deliverable(
    project_id: int,
    deliverable_id: int,
    payload: DeliverableUpdate,
    _: User = Depends(require_roles(DEV_ADMINS)),
    db: Session = Depends(get_db),
):
    d = db.get(Deliverable, deliverable_id)
    if not d or d.project_id != project_id:
        raise HTTPException(status_code=404, detail="Deliverable not found")
    data = payload.model_dump(exclude_unset=True)
    if "client_visible" in data and data["client_visible"] is not None:
        data["client_visible"] = 1 if data["client_visible"] else 0
    for k, v in data.items():
        setattr(d, k, v)
    db.commit()
    db.refresh(d)
    return _to_out(db, d)


@router.delete("/{deliverable_id}", status_code=204)
def delete_deliverable(
    project_id: int,
    deliverable_id: int,
    _: User = Depends(require_roles(DEV_ADMINS)),
    db: Session = Depends(get_db),
):
    d = db.get(Deliverable, deliverable_id)
    if not d or d.project_id != project_id:
        raise HTTPException(status_code=404, detail="Deliverable not found")
    db.delete(d)
    db.commit()


# --------------------------- AI analysis subpanel ----------------------- #
@router.post("/{deliverable_id}/analyze", response_model=AIAnalysisOut)
def analyze_deliverable(
    project_id: int,
    deliverable_id: int,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Run Grok analysis of this deliverable against the project master plan."""
    project = _get_project_or_404(db, project_id)
    d = db.get(Deliverable, deliverable_id)
    if not d or d.project_id != project_id:
        raise HTTPException(status_code=404, detail="Deliverable not found")

    result = grok.analyze_deliverable(
        master_plan=project.master_plan,
        title=d.title,
        description=d.description,
        acceptance=d.acceptance_criteria,
    )

    def _as_lines(value) -> str:
        if isinstance(value, list):
            return "\n".join(str(v) for v in value)
        return str(value or "")

    analysis = AIAnalysis(
        deliverable_id=d.id,
        score=float(result.get("score", 0) or 0),
        summary=result.get("summary", ""),
        strengths=_as_lines(result.get("strengths")),
        gaps=_as_lines(result.get("gaps")),
        recommendations=_as_lines(result.get("recommendations")),
        model=result.get("_model", grok.model if grok.enabled else "mock"),
        is_mock=1 if result.get("_mock") else 0,
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)
    return analysis


@router.get("/{deliverable_id}/analyses", response_model=list[AIAnalysisOut])
def list_analyses(
    project_id: int,
    deliverable_id: int,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    d = db.get(Deliverable, deliverable_id)
    if not d or d.project_id != project_id:
        raise HTTPException(status_code=404, detail="Deliverable not found")
    return (
        db.query(AIAnalysis)
        .filter(AIAnalysis.deliverable_id == deliverable_id)
        .order_by(AIAnalysis.created_at.desc())
        .all()
    )
