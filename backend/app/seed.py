"""Idempotent bootstrap: create tables and the initial admin user."""
import logging

from sqlalchemy import inspect

from app.auth import hash_password
from app.config import settings
from app.database import Base, SessionLocal, engine
from app.models import User, UserRole

logger = logging.getLogger("seed")


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    _ensure_admin()


def _ensure_admin() -> None:
    db = SessionLocal()
    try:
        if db.query(User).count() == 0:
            admin = User(
                email=settings.admin_email,
                name=settings.admin_name,
                password_hash=hash_password(settings.admin_password),
                role=UserRole.admin,
            )
            db.add(admin)
            db.commit()
            logger.info("Created bootstrap admin: %s", settings.admin_email)
    finally:
        db.close()


def db_ready() -> bool:
    try:
        return inspect(engine).has_table("users")
    except Exception:
        return False
