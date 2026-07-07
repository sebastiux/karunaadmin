"""Cross-project ticket monitoring for the dev team.

Aggregates all dev Kanban cards across every project into a single view so dev
admins can monitor delivery status org-wide.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import require_roles
from app.database import get_db
from app.models import KanbanCard, Project, User
from app.permissions import DEV_TEAM
from app.schemas import TicketOut

router = APIRouter(prefix="/api/tickets", tags=["tickets"])


@router.get("", response_model=list[TicketOut])
def list_tickets(
    assignee_id: int | None = None,
    _: User = Depends(require_roles(DEV_TEAM)),
    db: Session = Depends(get_db),
):
    q = (
        db.query(KanbanCard, Project.name, User.name)
        .join(Project, KanbanCard.project_id == Project.id)
        .outerjoin(User, KanbanCard.assignee_id == User.id)
    )
    if assignee_id is not None:
        q = q.filter(KanbanCard.assignee_id == assignee_id)
    rows = q.order_by(KanbanCard.updated_at.desc()).all()

    return [
        TicketOut(
            id=card.id,
            project_id=card.project_id,
            project_name=project_name,
            ticket_number=card.ticket_number or "",
            title=card.title,
            description=card.description,
            column=card.column,
            assignee_id=card.assignee_id,
            assignee_name=assignee_name,
            pr_url=card.pr_url,
            priority=card.priority,
            updated_at=card.updated_at,
        )
        for card, project_name, assignee_name in rows
    ]
