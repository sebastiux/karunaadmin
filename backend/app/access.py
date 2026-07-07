"""Project-level access control.

Internal users (dev team / admins) can access every project. External users
(clients) can only access projects they are a member of. Commercial users are
not project members and have no project access.
"""
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import ProjectMember, User
from app.permissions import DEV_TEAM

_INTERNAL = {r.value for r in DEV_TEAM}


def is_internal(user: User) -> bool:
    return user.role in _INTERNAL


def is_member(db: Session, user_id: int, project_id: int) -> bool:
    return (
        db.query(ProjectMember)
        .filter(ProjectMember.project_id == project_id, ProjectMember.user_id == user_id)
        .first()
        is not None
    )


def can_access_project(db: Session, user: User, project_id: int) -> bool:
    return is_internal(user) or is_member(db, user.id, project_id)


def require_project_access(db: Session, user: User, project_id: int) -> None:
    if not can_access_project(db, user, project_id):
        raise HTTPException(status_code=403, detail="You don't have access to this project")


def ensure_member(db: Session, user_id: int, project_id: int) -> None:
    """Idempotently grant a user membership of a project."""
    if not is_member(db, user_id, project_id):
        db.add(ProjectMember(project_id=project_id, user_id=user_id))
        db.commit()
