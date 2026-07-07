"""Code-review Kanban board. Deliberately AI-free; multi-developer follow-up."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_roles
from app.database import get_db
from app.models import KanbanCard, Project, User
from app.permissions import DEV_TEAM
from app.schemas import KanbanCardCreate, KanbanCardOut, KanbanCardUpdate

router = APIRouter(prefix="/api/projects/{project_id}/cards", tags=["kanban"])


def _to_out(db: Session, c: KanbanCard) -> KanbanCardOut:
    out = KanbanCardOut.model_validate(c)
    if c.assignee_id:
        user = db.get(User, c.assignee_id)
        out.assignee_name = user.name if user else None
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


@router.post("", response_model=KanbanCardOut, status_code=201)
def create_card(
    project_id: int,
    payload: KanbanCardCreate,
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
    db.commit()
    db.refresh(card)
    return _to_out(db, card)


@router.patch("/{card_id}", response_model=KanbanCardOut)
def update_card(
    project_id: int,
    card_id: int,
    payload: KanbanCardUpdate,
    _: User = Depends(require_roles(DEV_TEAM)),
    db: Session = Depends(get_db),
):
    card = db.get(KanbanCard, card_id)
    if not card or card.project_id != project_id:
        raise HTTPException(status_code=404, detail="Card not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(card, k, v)
    db.commit()
    db.refresh(card)
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
