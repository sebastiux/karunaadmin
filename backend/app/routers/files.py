"""Project file uploads (PDF / DOCX / any). Stored in the DB; text extracted."""
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.access import require_project_access
from app.auth import get_current_user, require_roles
from app.database import get_db
from app.models import Project, ProjectFile, User
from app.permissions import DEV_ADMINS
from app.schemas import FileUploadResult, ProjectFileOut
from app.services.extract import extract_text

router = APIRouter(prefix="/api/projects/{project_id}/files", tags=["files"])

MAX_BYTES = 25 * 1024 * 1024  # 25 MB


def _project_or_404(db: Session, project_id: int) -> Project:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def _to_out(f: ProjectFile) -> ProjectFileOut:
    out = ProjectFileOut.model_validate(f)
    out.extracted_chars = len(f.extracted_text or "")
    return out


@router.get("", response_model=list[ProjectFileOut])
def list_files(
    project_id: int,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _project_or_404(db, project_id)
    require_project_access(db, current, project_id)
    files = (
        db.query(ProjectFile)
        .filter(ProjectFile.project_id == project_id)
        .order_by(ProjectFile.created_at.desc())
        .all()
    )
    return [_to_out(f) for f in files]


@router.post("", response_model=FileUploadResult, status_code=201)
async def upload_file(
    project_id: int,
    file: UploadFile = File(...),
    user: User = Depends(require_roles(DEV_ADMINS)),
    db: Session = Depends(get_db),
):
    _project_or_404(db, project_id)
    data = await file.read()
    if len(data) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds 25 MB limit")

    text = extract_text(file.filename or "", file.content_type or "", data)
    pf = ProjectFile(
        project_id=project_id,
        filename=file.filename or "upload",
        content_type=file.content_type or "application/octet-stream",
        size=len(data),
        data=data,
        extracted_text=text,
        uploaded_by=user.id,
    )
    db.add(pf)
    db.commit()
    db.refresh(pf)
    return FileUploadResult(file=_to_out(pf), extracted_text=text)


@router.get("/{file_id}/download")
def download_file(
    project_id: int,
    file_id: int,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_project_access(db, current, project_id)
    pf = db.get(ProjectFile, file_id)
    if not pf or pf.project_id != project_id:
        raise HTTPException(status_code=404, detail="File not found")
    return Response(
        content=pf.data,
        media_type=pf.content_type or "application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{pf.filename}"'},
    )


@router.delete("/{file_id}", status_code=204)
def delete_file(
    project_id: int,
    file_id: int,
    _: User = Depends(require_roles(DEV_ADMINS)),
    db: Session = Depends(get_db),
):
    pf = db.get(ProjectFile, file_id)
    if not pf or pf.project_id != project_id:
        raise HTTPException(status_code=404, detail="File not found")
    db.delete(pf)
    db.commit()
