"""Code-review Kanban board. Deliberately AI-free; multi-developer follow-up."""
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
from app.models import KanbanCard, KanbanCardImage, Project, User
from app.permissions import DEV_TEAM
from app.schemas import (
    KanbanCardCreate,
    KanbanCardImageOut,
    KanbanCardOut,
    KanbanCardUpdate,
)
from app.services import notify

router = APIRouter(prefix="/api/projects/{project_id}/cards", tags=["kanban"])

MAX_IMAGE_BYTES = 15 * 1024 * 1024


def _to_out(db: Session, c: KanbanCard) -> KanbanCardOut:
    out = KanbanCardOut.model_validate(c)
    if c.assignee_id:
        user = db.get(User, c.assignee_id)
        out.assignee_name = user.name if user else None
    out.image_count = (
        db.query(KanbanCardImage).filter(KanbanCardImage.card_id == c.id).count()
    )
    return out


def _project_or_404(db: Session, project_id: int) -> Project:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.get("", response_model=list[KanbanCardOut])
def list_cards(
    project_id: int,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _project_or_404(db, project_id)
    cards = (
        db.query(KanbanCard)
        .filter(KanbanCard.project_id == project_id)
        .order_by(KanbanCard.order, KanbanCard.id)
        .all()
    )
    return [_to_out(db, c) for c in cards]


def _notify_assignee(background: BackgroundTasks, db: Session, card: KanbanCard):
    if not card.assignee_id:
        return
    assignee = db.get(User, card.assignee_id)
    project = db.get(Project, card.project_id)
    if assignee and project:
        background.add_task(
            notify.dev_card_assigned,
            assignee.email, assignee.name, card.title, project.name, project.id,
        )


@router.post("", response_model=KanbanCardOut, status_code=201)
def create_card(
    project_id: int,
    payload: KanbanCardCreate,
    background: BackgroundTasks,
    _: User = Depends(require_roles(DEV_TEAM)),
    db: Session = Depends(get_db),
):
    _project_or_404(db, project_id)
    # Place new card at the end of its column.
    max_order = (
        db.query(KanbanCard)
        .filter(KanbanCard.project_id == project_id, KanbanCard.column == payload.column)
        .count()
    )
    card = KanbanCard(
        project_id=project_id,
        title=payload.title,
        description=payload.description,
        column=payload.column,
        assignee_id=payload.assignee_id,
        pr_url=payload.pr_url,
        priority=payload.priority,
        order=max_order,
    )
    db.add(card)
    db.flush()  # assign an id so we can build the ticket number
    card.ticket_number = f"TKT-{card.id:04d}"
    db.commit()
    db.refresh(card)
    _notify_assignee(background, db, card)
    return _to_out(db, card)


@router.patch("/{card_id}", response_model=KanbanCardOut)
def update_card(
    project_id: int,
    card_id: int,
    payload: KanbanCardUpdate,
    background: BackgroundTasks,
    _: User = Depends(require_roles(DEV_TEAM)),
    db: Session = Depends(get_db),
):
    card = db.get(KanbanCard, card_id)
    if not card or card.project_id != project_id:
        raise HTTPException(status_code=404, detail="Card not found")
    prev_assignee = card.assignee_id
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(card, k, v)
    db.commit()
    db.refresh(card)
    if card.assignee_id and card.assignee_id != prev_assignee:
        _notify_assignee(background, db, card)
    return _to_out(db, card)


@router.delete("/{card_id}", status_code=204)
def delete_card(
    project_id: int,
    card_id: int,
    _: User = Depends(require_roles(DEV_TEAM)),
    db: Session = Depends(get_db),
):
    card = db.get(KanbanCard, card_id)
    if not card or card.project_id != project_id:
        raise HTTPException(status_code=404, detail="Card not found")
    db.delete(card)
    db.commit()


# --------------------------- Card reference images ---------------------- #
def _card_or_404(db: Session, project_id: int, card_id: int) -> KanbanCard:
    card = db.get(KanbanCard, card_id)
    if not card or card.project_id != project_id:
        raise HTTPException(status_code=404, detail="Card not found")
    return card


@router.get("/{card_id}/images", response_model=list[KanbanCardImageOut])
def list_images(
    project_id: int,
    card_id: int,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _card_or_404(db, project_id, card_id)
    return (
        db.query(KanbanCardImage)
        .filter(KanbanCardImage.card_id == card_id)
        .order_by(KanbanCardImage.created_at)
        .all()
    )


@router.post("/{card_id}/images", response_model=KanbanCardImageOut, status_code=201)
async def upload_image(
    project_id: int,
    card_id: int,
    file: UploadFile = File(...),
    user: User = Depends(require_roles(DEV_TEAM)),
    db: Session = Depends(get_db),
):
    _card_or_404(db, project_id, card_id)
    data = await file.read()
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Image exceeds 15 MB limit")
    ctype = file.content_type or "image/png"
    if not ctype.startswith("image/"):
        raise HTTPException(status_code=400, detail="Only image files are allowed")
    img = KanbanCardImage(
        card_id=card_id,
        filename=file.filename or "pasted-image.png",
        content_type=ctype,
        size=len(data),
        data=data,
        uploaded_by=user.id,
    )
    db.add(img)
    db.commit()
    db.refresh(img)
    return img


@router.get("/{card_id}/images/{image_id}/raw")
def get_image(
    project_id: int,
    card_id: int,
    image_id: int,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _card_or_404(db, project_id, card_id)
    img = db.get(KanbanCardImage, image_id)
    if not img or img.card_id != card_id:
        raise HTTPException(status_code=404, detail="Image not found")
    return Response(content=img.data, media_type=img.content_type or "image/png")


@router.delete("/{card_id}/images/{image_id}", status_code=204)
def delete_image(
    project_id: int,
    card_id: int,
    image_id: int,
    _: User = Depends(require_roles(DEV_TEAM)),
    db: Session = Depends(get_db),
):
    _card_or_404(db, project_id, card_id)
    img = db.get(KanbanCardImage, image_id)
    if not img or img.card_id != card_id:
        raise HTTPException(status_code=404, detail="Image not found")
    db.delete(img)
    db.commit()
