"""Project lifecycle: create, list, submit master plan (triggers AI generation)."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, selectinload

from app.access import can_access_project, is_internal, require_project_access
from app.auth import get_current_user, require_roles
from app.database import get_db
from app.permissions import DEV_ADMINS, DEV_TEAM
from app.models import (
    Deliverable,
    PlanPoint,
    Project,
    ProjectMember,
    ProjectStatus,
    User,
    UserRole,
)
from app.schemas import (
    MasterPlanSubmit,
    ProjectCreate,
    ProjectDetail,
    ProjectOut,
    UserOut,
)
from app.services.grok import grok

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.get("", response_model=list[ProjectOut])
def list_projects(
    current: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    q = db.query(Project).order_by(Project.created_at.desc())
    if is_internal(current):
        return q.all()
    # External users (clients) only see projects they're a member of.
    member_ids = [
        m.project_id
        for m in db.query(ProjectMember).filter(ProjectMember.user_id == current.id).all()
    ]
    if not member_ids:
        return []
    return q.filter(Project.id.in_(member_ids)).all()


@router.post("", response_model=ProjectOut, status_code=201)
def create_project(
    payload: ProjectCreate,
    _: User = Depends(require_roles(DEV_ADMINS)),
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
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = db.query(Project).options(
        selectinload(Project.plan_points)
    ).get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    require_project_access(db, current, project_id)
    # Order plan points deterministically for the response.
    project.plan_points.sort(key=lambda p: p.order)
    return project


@router.post("/{project_id}/master-plan", response_model=ProjectDetail)
def submit_master_plan(
    project_id: int,
    payload: MasterPlanSubmit,
    _: User = Depends(require_roles(DEV_ADMINS)),
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
    _: User = Depends(require_roles(DEV_ADMINS)),
    db: Session = Depends(get_db),
):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    db.delete(project)
    db.commit()


# --------------------------- Members / access -------------------------- #
@router.get("/{project_id}/members", response_model=list[UserOut])
def list_members(
    project_id: int,
    _: User = Depends(require_roles(DEV_ADMINS)),
    db: Session = Depends(get_db),
):
    rows = db.query(ProjectMember).filter(ProjectMember.project_id == project_id).all()
    ids = [r.user_id for r in rows]
    if not ids:
        return []
    return db.query(User).filter(User.id.in_(ids)).all()


@router.post("/{project_id}/members/{user_id}", response_model=list[UserOut], status_code=201)
def add_member(
    project_id: int,
    user_id: int,
    _: User = Depends(require_roles(DEV_ADMINS)),
    db: Session = Depends(get_db),
):
    if not db.get(Project, project_id) or not db.get(User, user_id):
        raise HTTPException(status_code=404, detail="Project or user not found")
    exists = (
        db.query(ProjectMember)
        .filter(ProjectMember.project_id == project_id, ProjectMember.user_id == user_id)
        .first()
    )
    if not exists:
        db.add(ProjectMember(project_id=project_id, user_id=user_id))
        db.commit()
    return list_members(project_id, _, db)


@router.delete("/{project_id}/members/{user_id}", status_code=204)
def remove_member(
    project_id: int,
    user_id: int,
    _: User = Depends(require_roles(DEV_ADMINS)),
    db: Session = Depends(get_db),
):
    db.query(ProjectMember).filter(
        ProjectMember.project_id == project_id, ProjectMember.user_id == user_id
    ).delete()
    db.commit()


@router.get("/{project_id}/assignable-users", response_model=list[UserOut])
def assignable_users(
    project_id: int,
    _: User = Depends(require_roles(DEV_TEAM)),
    db: Session = Depends(get_db),
):
    """Users a deliverable can be assigned to: all internal users + the clients
    who are members of this project."""
    internal_roles = [
        UserRole.admin.value, UserRole.admin_dev.value, UserRole.dev.value,
    ]
    internal = db.query(User).filter(User.role.in_(internal_roles)).all()
    member_ids = [
        m.user_id
        for m in db.query(ProjectMember).filter(ProjectMember.project_id == project_id).all()
    ]
    members = (
        db.query(User).filter(User.id.in_(member_ids)).all() if member_ids else []
    )
    # de-dup while preserving order
    seen, out = set(), []
    for u in internal + members:
        if u.id not in seen:
            seen.add(u.id)
            out.append(u)
    return out
