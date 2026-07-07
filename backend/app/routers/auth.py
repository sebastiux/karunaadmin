"""Auth + minimal user management endpoints."""
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import (
    create_access_token,
    get_current_user,
    hash_password,
    require_roles,
    verify_password,
)
from app.database import get_db
from app.models import Project, ProjectMember, User, UserRole
from app.permissions import ALL_ADMINS
from app.services import notify
from app.schemas import LoginRequest, TokenResponse, UserCreate, UserOut

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
        )
    token = create_access_token(user)
    return TokenResponse(access_token=token, user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
def me(current: User = Depends(get_current_user)):
    return current


@router.get("/users", response_model=list[UserOut])
def list_users(
    _: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    # Any authenticated user may list users (needed for assignee pickers).
    return db.query(User).order_by(User.name).all()


# Which roles each admin type is allowed to create.
_CREATABLE: dict[str, set[UserRole]] = {
    UserRole.admin.value: set(UserRole),  # super admin: any role
    UserRole.admin_dev.value: {UserRole.dev, UserRole.admin_dev, UserRole.client},
    UserRole.admin_comercial.value: {UserRole.comercial, UserRole.admin_comercial},
}


@router.post("/users", response_model=UserOut, status_code=201)
def create_user(
    payload: UserCreate,
    background: BackgroundTasks,
    creator: User = Depends(require_roles(ALL_ADMINS)),
    db: Session = Depends(get_db),
):
    allowed = _CREATABLE.get(creator.role, set())
    if payload.role not in {r.value for r in allowed}:
        raise HTTPException(
            status_code=403,
            detail=f"Your role ({creator.role}) cannot create '{payload.role}' users.",
        )
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=409, detail="Email already registered")
    role_value = payload.role.value if hasattr(payload.role, "value") else payload.role
    user = User(
        email=payload.email,
        name=payload.name,
        password_hash=hash_password(payload.password),
        role=role_value,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    # Grant the user access to the selected projects (relevant for clients).
    for pid in set(payload.project_ids):
        if db.get(Project, pid):
            db.add(ProjectMember(project_id=pid, user_id=user.id))
    db.commit()
    # Welcome email with credentials (background; no-op without Resend key).
    background.add_task(
        notify.user_welcome, user.email, user.name, role_value, payload.password
    )
    return user
