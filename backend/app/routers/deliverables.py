"""Deliverables panel, AI-analysis subpanel (INTERNAL only), and deliverable
document uploads (which assigned clients may submit)."""
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    UploadFile,
)
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_roles
from app.database import get_db
from app.models import (
    AIAnalysis,
    Deliverable,
    DeliverableFile,
    DeliverableStatus,
    Project,
    User,
    UserRole,
)
from app.permissions import DEV_ADMINS, DEV_TEAM
from app.schemas import (
    AIAnalysisOut,
    DeliverableCreate,
    DeliverableFileOut,
    DeliverableOut,
    DeliverableUpdate,
)
from app.services import notify
from app.services.grok import grok

router = APIRouter(prefix="/api/projects/{project_id}/deliverables", tags=["deliverables"])

_DEV_TEAM_VALUES = {r.value for r in DEV_TEAM}
MAX_BYTES = 25 * 1024 * 1024


def _is_internal(user: User) -> bool:
    """Internal = dev team/admins. Clients and commercial users are external."""
    return user.role in _DEV_TEAM_VALUES


def _latest_analysis(db: Session, deliverable_id: int) -> AIAnalysis | None:
    return (
        db.query(AIAnalysis)
        .filter(AIAnalysis.deliverable_id == deliverable_id)
        .order_by(AIAnalysis.created_at.desc(), AIAnalysis.id.desc())
        .first()
    )


def _to_out(db: Session, d: Deliverable, viewer: User) -> DeliverableOut:
    out = DeliverableOut.model_validate(d)
    out.file_count = (
        db.query(DeliverableFile)
        .filter(DeliverableFile.deliverable_id == d.id)
        .count()
    )
    if d.assignee_id:
        u = db.get(User, d.assignee_id)
        out.assignee_name = u.name if u else None
    # AI analysis is internal-only: never expose it to clients/externals.
    if _is_internal(viewer):
        latest = _latest_analysis(db, d.id)
        if latest:
            out.latest_analysis = AIAnalysisOut.model_validate(latest)
    else:
        out.latest_analysis = None
    return out


def _get_project_or_404(db: Session, project_id: int) -> Project:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def _get_deliverable(db: Session, project_id: int, deliverable_id: int) -> Deliverable:
    d = db.get(Deliverable, deliverable_id)
    if not d or d.project_id != project_id:
        raise HTTPException(status_code=404, detail="Deliverable not found")
    return d


def _can_access(user: User, d: Deliverable) -> bool:
    return _is_internal(user) or d.assignee_id == user.id


# --------------------------- CRUD --------------------------------------- #
@router.get("", response_model=list[DeliverableOut])
def list_deliverables(
    project_id: int,
    client_only: bool = False,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _get_project_or_404(db, project_id)
    q = db.query(Deliverable).filter(Deliverable.project_id == project_id)
    # Externals (clients) only ever see client-visible deliverables.
    if client_only or not _is_internal(current):
        q = q.filter(Deliverable.client_visible == 1)
    items = q.order_by(Deliverable.plan_point_id, Deliverable.order, Deliverable.id).all()
    return [_to_out(db, d, current) for d in items]


@router.post("", response_model=DeliverableOut, status_code=201)
def create_deliverable(
    project_id: int,
    payload: DeliverableCreate,
    background: BackgroundTasks,
    _: User = Depends(require_roles(DEV_ADMINS)),
    db: Session = Depends(get_db),
):
    project = _get_project_or_404(db, project_id)
    d = Deliverable(
        project_id=project_id,
        plan_point_id=payload.plan_point_id,
        title=payload.title,
        description=payload.description,
        acceptance_criteria=payload.acceptance_criteria,
        client_visible=1 if payload.client_visible else 0,
        assignee_id=payload.assignee_id,
        ai_generated=0,
    )
    db.add(d)
    db.commit()
    db.refresh(d)
    if d.assignee_id:
        assignee = db.get(User, d.assignee_id)
        if assignee:
            background.add_task(
                notify.deliverable_assigned,
                assignee.email, assignee.name, d.title, project.name, project_id,
            )
    return _to_out(db, d, _)


@router.patch("/{deliverable_id}", response_model=DeliverableOut)
def update_deliverable(
    project_id: int,
    deliverable_id: int,
    payload: DeliverableUpdate,
    background: BackgroundTasks,
    user: User = Depends(require_roles(DEV_ADMINS)),
    db: Session = Depends(get_db),
):
    project = _get_project_or_404(db, project_id)
    d = _get_deliverable(db, project_id, deliverable_id)
    prev_assignee = d.assignee_id

    data = payload.model_dump(exclude_unset=True)
    if "client_visible" in data and data["client_visible"] is not None:
        data["client_visible"] = 1 if data["client_visible"] else 0
    for k, v in data.items():
        setattr(d, k, v)
    db.commit()
    db.refresh(d)

    if d.assignee_id and d.assignee_id != prev_assignee:
        assignee = db.get(User, d.assignee_id)
        if assignee:
            background.add_task(
                notify.deliverable_assigned,
                assignee.email, assignee.name, d.title, project.name, project_id,
            )
    return _to_out(db, d, user)


@router.delete("/{deliverable_id}", status_code=204)
def delete_deliverable(
    project_id: int,
    deliverable_id: int,
    _: User = Depends(require_roles(DEV_ADMINS)),
    db: Session = Depends(get_db),
):
    d = _get_deliverable(db, project_id, deliverable_id)
    db.delete(d)
    db.commit()


@router.post("/{deliverable_id}/submit", response_model=DeliverableOut)
def submit_deliverable(
    project_id: int,
    deliverable_id: int,
    background: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """The assignee (e.g. a client) marks their deliverable as submitted."""
    project = _get_project_or_404(db, project_id)
    d = _get_deliverable(db, project_id, deliverable_id)
    if not _can_access(user, d):
        raise HTTPException(status_code=403, detail="This deliverable isn't assigned to you")
    d.status = DeliverableStatus.submitted
    db.commit()
    db.refresh(d)

    admins = (
        db.query(User)
        .filter(User.role.in_([UserRole.admin.value, UserRole.admin_dev.value]))
        .all()
    )
    background.add_task(
        notify.deliverable_submitted,
        [a.email for a in admins], d.title, project.name, user.name, project_id,
    )
    return _to_out(db, d, user)


# --------------------------- AI analysis (INTERNAL ONLY) ---------------- #
@router.post("/{deliverable_id}/analyze", response_model=AIAnalysisOut)
def analyze_deliverable(
    project_id: int,
    deliverable_id: int,
    _: User = Depends(require_roles(DEV_TEAM)),  # internal only
    db: Session = Depends(get_db),
):
    project = _get_project_or_404(db, project_id)
    d = _get_deliverable(db, project_id, deliverable_id)

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
    _: User = Depends(require_roles(DEV_TEAM)),  # internal only
    db: Session = Depends(get_db),
):
    _get_deliverable(db, project_id, deliverable_id)
    return (
        db.query(AIAnalysis)
        .filter(AIAnalysis.deliverable_id == deliverable_id)
        .order_by(AIAnalysis.created_at.desc())
        .all()
    )


# --------------------------- Deliverable documents ---------------------- #
@router.get("/{deliverable_id}/files", response_model=list[DeliverableFileOut])
def list_deliverable_files(
    project_id: int,
    deliverable_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    d = _get_deliverable(db, project_id, deliverable_id)
    if not _can_access(user, d):
        raise HTTPException(status_code=403, detail="Not allowed")
    return (
        db.query(DeliverableFile)
        .filter(DeliverableFile.deliverable_id == deliverable_id)
        .order_by(DeliverableFile.created_at.desc())
        .all()
    )


@router.post("/{deliverable_id}/files", response_model=DeliverableFileOut, status_code=201)
async def upload_deliverable_file(
    project_id: int,
    deliverable_id: int,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    d = _get_deliverable(db, project_id, deliverable_id)
    # Dev admins, or the assigned user (which may be a client), may upload.
    if not (user.role in {r.value for r in DEV_ADMINS} or d.assignee_id == user.id):
        raise HTTPException(status_code=403, detail="Not allowed to upload here")
    data = await file.read()
    if len(data) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds 25 MB limit")
    df = DeliverableFile(
        deliverable_id=deliverable_id,
        filename=file.filename or "upload",
        content_type=file.content_type or "application/octet-stream",
        size=len(data),
        data=data,
        uploaded_by=user.id,
    )
    db.add(df)
    db.commit()
    db.refresh(df)
    return df


@router.get("/{deliverable_id}/files/{file_id}/download")
def download_deliverable_file(
    project_id: int,
    deliverable_id: int,
    file_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    d = _get_deliverable(db, project_id, deliverable_id)
    if not _can_access(user, d):
        raise HTTPException(status_code=403, detail="Not allowed")
    df = db.get(DeliverableFile, file_id)
    if not df or df.deliverable_id != deliverable_id:
        raise HTTPException(status_code=404, detail="File not found")
    return Response(
        content=df.data,
        media_type=df.content_type or "application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{df.filename}"'},
    )


@router.delete("/{deliverable_id}/files/{file_id}", status_code=204)
def delete_deliverable_file(
    project_id: int,
    deliverable_id: int,
    file_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _get_deliverable(db, project_id, deliverable_id)
    df = db.get(DeliverableFile, file_id)
    if not df or df.deliverable_id != deliverable_id:
        raise HTTPException(status_code=404, detail="File not found")
    # Dev admins can delete any; a uploader can delete their own.
    if not (user.role in {r.value for r in DEV_ADMINS} or df.uploaded_by == user.id):
        raise HTTPException(status_code=403, detail="Not allowed")
    db.delete(df)
    db.commit()
