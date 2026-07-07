"""Document requests: the internal team asks selected client users to upload
documentation for a project; those clients get an email + an in-app area."""
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

from app.access import is_internal, require_project_access
from app.auth import get_current_user, require_roles
from app.database import get_db
from app.models import (
    DocRequestStatus,
    DocumentRequest,
    DocumentRequestFile,
    DocumentRequestRecipient,
    Project,
    User,
    UserRole,
)
from app.permissions import DEV_ADMINS, DEV_TEAM
from app.schemas import DocRequestCreate, DocRequestFileOut, DocRequestOut

router = APIRouter(prefix="/api/projects/{project_id}/doc-requests", tags=["doc-requests"])

MAX_BYTES = 25 * 1024 * 1024


def _project_or_404(db: Session, project_id: int) -> Project:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def _recipient_ids(db: Session, request_id: int) -> list[int]:
    return [
        r.user_id
        for r in db.query(DocumentRequestRecipient)
        .filter(DocumentRequestRecipient.request_id == request_id)
        .all()
    ]


def _to_out(db: Session, req: DocumentRequest) -> DocRequestOut:
    rec_ids = _recipient_ids(db, req.id)
    names = []
    if rec_ids:
        names = [u.name for u in db.query(User).filter(User.id.in_(rec_ids)).all()]
    creator = db.get(User, req.created_by) if req.created_by else None
    files = (
        db.query(DocumentRequestFile)
        .filter(DocumentRequestFile.request_id == req.id)
        .order_by(DocumentRequestFile.created_at.desc())
        .all()
    )
    return DocRequestOut(
        id=req.id,
        project_id=req.project_id,
        title=req.title,
        description=req.description,
        status=req.status,
        created_by=req.created_by,
        created_by_name=creator.name if creator else None,
        created_at=req.created_at,
        recipient_ids=rec_ids,
        recipient_names=names,
        files=[DocRequestFileOut.model_validate(f) for f in files],
    )


def _get_request(db: Session, project_id: int, request_id: int) -> DocumentRequest:
    req = db.get(DocumentRequest, request_id)
    if not req or req.project_id != project_id:
        raise HTTPException(status_code=404, detail="Request not found")
    return req


def _can_act(db: Session, user: User, req: DocumentRequest) -> bool:
    return is_internal(user) or user.id in _recipient_ids(db, req.id)


@router.get("", response_model=list[DocRequestOut])
def list_requests(
    project_id: int,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _project_or_404(db, project_id)
    require_project_access(db, current, project_id)
    reqs = (
        db.query(DocumentRequest)
        .filter(DocumentRequest.project_id == project_id)
        .order_by(DocumentRequest.created_at.desc())
        .all()
    )
    if is_internal(current):
        return [_to_out(db, r) for r in reqs]
    # Clients only see requests addressed to them.
    return [_to_out(db, r) for r in reqs if current.id in _recipient_ids(db, r.id)]


@router.post("", response_model=DocRequestOut, status_code=201)
def create_request(
    project_id: int,
    payload: DocRequestCreate,
    background: BackgroundTasks,
    user: User = Depends(require_roles(DEV_TEAM)),
    db: Session = Depends(get_db),
):
    project = _project_or_404(db, project_id)
    req = DocumentRequest(
        project_id=project_id,
        title=payload.title,
        description=payload.description,
        created_by=user.id,
    )
    db.add(req)
    db.flush()
    # Only real users may be recipients.
    recipients = (
        db.query(User).filter(User.id.in_(payload.recipient_user_ids)).all()
        if payload.recipient_user_ids
        else []
    )
    for r in recipients:
        db.add(DocumentRequestRecipient(request_id=req.id, user_id=r.id))
    db.commit()
    db.refresh(req)

    # Email the selected client users.
    from app.services import notify
    for r in recipients:
        background.add_task(
            notify.doc_request_created,
            r.email, r.name, req.title, req.description, project.name, project_id,
        )
    return _to_out(db, req)


@router.patch("/{request_id}/status", response_model=DocRequestOut)
def set_status(
    project_id: int,
    request_id: int,
    status: str,
    _: User = Depends(require_roles(DEV_TEAM)),
    db: Session = Depends(get_db),
):
    req = _get_request(db, project_id, request_id)
    if status not in {s.value for s in DocRequestStatus}:
        raise HTTPException(status_code=400, detail="Invalid status")
    req.status = status
    db.commit()
    db.refresh(req)
    return _to_out(db, req)


@router.delete("/{request_id}", status_code=204)
def delete_request(
    project_id: int,
    request_id: int,
    _: User = Depends(require_roles(DEV_ADMINS)),
    db: Session = Depends(get_db),
):
    req = _get_request(db, project_id, request_id)
    db.delete(req)
    db.commit()


# --------------------------- Files -------------------------------------- #
@router.post("/{request_id}/files", response_model=DocRequestFileOut, status_code=201)
async def upload_request_file(
    project_id: int,
    request_id: int,
    background: BackgroundTasks,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = _project_or_404(db, project_id)
    req = _get_request(db, project_id, request_id)
    if not _can_act(db, user, req):
        raise HTTPException(status_code=403, detail="This request isn't addressed to you")
    data = await file.read()
    if len(data) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds 25 MB limit")
    df = DocumentRequestFile(
        request_id=request_id,
        filename=file.filename or "upload",
        content_type=file.content_type or "application/octet-stream",
        size=len(data),
        data=data,
        uploaded_by=user.id,
    )
    db.add(df)
    # A client upload moves the request to "submitted" and notifies the team.
    if not is_internal(user) and req.status == DocRequestStatus.open.value:
        req.status = DocRequestStatus.submitted.value
    db.commit()
    db.refresh(df)

    if not is_internal(user):
        from app.services import notify
        admins = (
            db.query(User)
            .filter(User.role.in_([UserRole.admin.value, UserRole.admin_dev.value]))
            .all()
        )
        emails = {a.email for a in admins}
        if req.created_by:
            creator = db.get(User, req.created_by)
            if creator:
                emails.add(creator.email)
        background.add_task(
            notify.doc_request_submitted,
            list(emails), req.title, project.name, user.name, project_id,
        )
    return df


@router.get("/{request_id}/files/{file_id}/download")
def download_request_file(
    project_id: int,
    request_id: int,
    file_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    req = _get_request(db, project_id, request_id)
    if not _can_act(db, user, req):
        raise HTTPException(status_code=403, detail="Not allowed")
    df = db.get(DocumentRequestFile, file_id)
    if not df or df.request_id != request_id:
        raise HTTPException(status_code=404, detail="File not found")
    return Response(
        content=df.data,
        media_type=df.content_type or "application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{df.filename}"'},
    )


@router.delete("/{request_id}/files/{file_id}", status_code=204)
def delete_request_file(
    project_id: int,
    request_id: int,
    file_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    req = _get_request(db, project_id, request_id)
    df = db.get(DocumentRequestFile, file_id)
    if not df or df.request_id != request_id:
        raise HTTPException(status_code=404, detail="File not found")
    if not (user.role in {r.value for r in DEV_ADMINS} or df.uploaded_by == user.id):
        raise HTTPException(status_code=403, detail="Not allowed")
    db.delete(df)
    db.commit()
