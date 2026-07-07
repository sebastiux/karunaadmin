"""Project lifecycle: create, list, submit master plan (triggers AI generation)."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, selectinload

from app.auth import get_current_user, require_role
from app.database import get_db
from app.models import (
    Deliverable,
    PlanPoint,
    Project,
    ProjectStatus,
    User,
    UserRole,
)
from app.schemas import (
    MasterPlanSubmit,
    ProjectCreate,
    ProjectDetail,
    ProjectOut,
)
from app.services.grok import grok

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.get("", response_model=list[ProjectOut])
def list_projects(
    _: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    return db.query(Project).order_by(Project.created_at.desc()).all()


@router.post("", response_model=ProjectOut, status_code=201)
def create_project(
    payload: ProjectCreate,
    _: User = Depends(require_role(UserRole.admin)),
    db: Session = Depends(get_db),
):
    project = Project(name=payload.name, description=payload.description)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("/{project_id}", response_model=ProjectDetail)
def get_project(
    project_id: int,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = db.query(Project).options(
        selectinload(Project.plan_points)
    ).get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    # Order plan points deterministically for the response.
    project.plan_points.sort(key=lambda p: p.order)
    return project


@router.post("/{project_id}/master-plan", response_model=ProjectDetail)
def submit_master_plan(
    project_id: int,
    payload: MasterPlanSubmit,
    _: User = Depends(require_role(UserRole.admin)),
    db: Session = Depends(get_db),
):
    """Submit the master plan. This is step 1 of configuring a project.

    When ``generate_deliverables`` is true, Grok parses the plan into plan
    points and generates deliverables for each. Re-submitting replaces the
    previously generated plan points and AI-generated deliverables (manually
    added deliverables are preserved).
    """
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    project.master_plan = payload.master_plan

    if payload.generate_deliverables:
        # Clear prior generated artifacts so re-submitting is idempotent.
        db.query(Deliverable).filter(
            Deliverable.project_id == project_id,
            Deliverable.ai_generated == 1,
        ).delete(synchronize_session=False)
        db.query(PlanPoint).filter(PlanPoint.project_id == project_id).delete(
            synchronize_session=False
        )

        result = grok.generate_deliverables_from_plan(payload.master_plan)
        for p_idx, point in enumerate(result.get("plan_points", [])):
            plan_point = PlanPoint(
                project_id=project_id,
                title=(point.get("title") or "Objective")[:500],
                description=point.get("description", ""),
                order=p_idx,
            )
            db.add(plan_point)
            db.flush()  # get plan_point.id
            for d_idx, deliv in enumerate(point.get("deliverables", [])):
                db.add(
                    Deliverable(
                        project_id=project_id,
                        plan_point_id=plan_point.id,
                        title=(deliv.get("title") or "Deliverable")[:500],
                        description=deliv.get("description", ""),
                        acceptance_criteria=deliv.get("acceptance_criteria", ""),
                        ai_generated=1,
                        order=d_idx,
                    )
                )
        project.status = ProjectStatus.active

    db.commit()
    db.refresh(project)
    project.plan_points.sort(key=lambda p: p.order)
    return project


@router.delete("/{project_id}", status_code=204)
def delete_project(
    project_id: int,
    _: User = Depends(require_role(UserRole.admin)),
    db: Session = Depends(get_db),
):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    db.delete(project)
    db.commit()
