"""Commercial workspace — global Kanban boards for sourcing new IT projects.

AI-free, worked by the commercial team. Board management is limited to
commercial admins; card CRUD/assignment is open to the whole commercial team.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import require_roles
from app.database import get_db
from app.models import CommercialBoard, CommercialCard, User
from app.permissions import COMMERCIAL_ADMINS, COMMERCIAL_TEAM
from app.schemas import (
    CommercialBoardCreate,
    CommercialBoardOut,
    CommercialCardCreate,
    CommercialCardOut,
    CommercialCardUpdate,
)

router = APIRouter(prefix="/api/commercial", tags=["commercial"])


def _card_out(db: Session, c: CommercialCard) -> CommercialCardOut:
    out = CommercialCardOut.model_validate(c)
    if c.assignee_id:
        u = db.get(User, c.assignee_id)
        out.assignee_name = u.name if u else None
    return out


# ------------------------------ Boards ---------------------------------- #
@router.get("/boards", response_model=list[CommercialBoardOut])
def list_boards(
    _: User = Depends(require_roles(COMMERCIAL_TEAM)),
    db: Session = Depends(get_db),
):
    return db.query(CommercialBoard).order_by(CommercialBoard.created_at).all()


@router.post("/boards", response_model=CommercialBoardOut, status_code=201)
def create_board(
    payload: CommercialBoardCreate,
    _: User = Depends(require_roles(COMMERCIAL_ADMINS)),
    db: Session = Depends(get_db),
):
    board = CommercialBoard(name=payload.name, description=payload.description)
    db.add(board)
    db.commit()
    db.refresh(board)
    return board


@router.delete("/boards/{board_id}", status_code=204)
def delete_board(
    board_id: int,
    _: User = Depends(require_roles(COMMERCIAL_ADMINS)),
    db: Session = Depends(get_db),
):
    board = db.get(CommercialBoard, board_id)
    if not board:
        raise HTTPException(status_code=404, detail="Board not found")
    db.delete(board)
    db.commit()


# ------------------------------ Cards ----------------------------------- #
@router.get("/boards/{board_id}/cards", response_model=list[CommercialCardOut])
def list_cards(
    board_id: int,
    _: User = Depends(require_roles(COMMERCIAL_TEAM)),
    db: Session = Depends(get_db),
):
    if not db.get(CommercialBoard, board_id):
        raise HTTPException(status_code=404, detail="Board not found")
    cards = (
        db.query(CommercialCard)
        .filter(CommercialCard.board_id == board_id)
        .order_by(CommercialCard.order, CommercialCard.id)
        .all()
    )
    return [_card_out(db, c) for c in cards]


@router.post("/boards/{board_id}/cards", response_model=CommercialCardOut, status_code=201)
def create_card(
    board_id: int,
    payload: CommercialCardCreate,
    _: User = Depends(require_roles(COMMERCIAL_TEAM)),
    db: Session = Depends(get_db),
):
    if not db.get(CommercialBoard, board_id):
        raise HTTPException(status_code=404, detail="Board not found")
    order = (
        db.query(CommercialCard)
        .filter(CommercialCard.board_id == board_id, CommercialCard.column == payload.column)
        .count()
    )
    card = CommercialCard(
        board_id=board_id,
        title=payload.title,
        description=payload.description,
        company=payload.company,
        contact=payload.contact,
        estimated_value=payload.estimated_value,
        column=payload.column,
        assignee_id=payload.assignee_id,
        priority=payload.priority,
        order=order,
    )
    db.add(card)
    db.commit()
    db.refresh(card)
    return _card_out(db, card)


@router.patch("/cards/{card_id}", response_model=CommercialCardOut)
def update_card(
    card_id: int,
    payload: CommercialCardUpdate,
    _: User = Depends(require_roles(COMMERCIAL_TEAM)),
    db: Session = Depends(get_db),
):
    card = db.get(CommercialCard, card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(card, k, v)
    db.commit()
    db.refresh(card)
    return _card_out(db, card)


@router.delete("/cards/{card_id}", status_code=204)
def delete_card(
    card_id: int,
    _: User = Depends(require_roles(COMMERCIAL_TEAM)),
    db: Session = Depends(get_db),
):
    card = db.get(CommercialCard, card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    db.delete(card)
    db.commit()
