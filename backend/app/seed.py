"""Idempotent bootstrap: create tables, migrate the live schema, seed defaults."""
import logging

from sqlalchemy import inspect, text

from app.auth import hash_password
from app.config import settings
from app.database import Base, SessionLocal, engine
from app.models import CommercialBoard, User, UserRole

logger = logging.getLogger("seed")


def init_db() -> None:
    Base.metadata.create_all(bind=engine)  # creates any missing tables
    _migrate_schema()
    _ensure_admin()
    _ensure_commercial_board()


def _migrate_schema() -> None:
    """Bring an already-deployed database up to date without a migration tool.

    The `users.role` column was originally a MySQL ENUM('admin','developer',
    'client'); the role set has since grown. Widen it to VARCHAR so new roles
    are accepted, and map the legacy 'developer' value to 'dev'.
    """
    if engine.dialect.name != "mysql":
        return  # SQLite stores Enum as VARCHAR already — nothing to do.
    try:
        with engine.begin() as conn:
            col = conn.execute(
                text(
                    "SELECT DATA_TYPE FROM information_schema.COLUMNS "
                    "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'users' "
                    "AND COLUMN_NAME = 'role'"
                )
            ).scalar()
            if col and col.lower() == "enum":
                conn.execute(
                    text(
                        "ALTER TABLE users MODIFY COLUMN role "
                        "VARCHAR(32) NOT NULL DEFAULT 'dev'"
                    )
                )
                logger.info("Migrated users.role ENUM -> VARCHAR(32)")
            # Legacy value rename (safe to run repeatedly).
            conn.execute(
                text("UPDATE users SET role = 'dev' WHERE role = 'developer'")
            )
    except Exception as exc:  # never block startup on migration hiccups
        logger.warning("Schema migration skipped: %s", exc)


def _ensure_admin() -> None:
    db = SessionLocal()
    try:
        if db.query(User).count() == 0:
            admin = User(
                email=settings.admin_email,
                name=settings.admin_name,
                password_hash=hash_password(settings.admin_password),
                role=UserRole.admin.value,  # super admin
            )
            db.add(admin)
            db.commit()
            logger.info("Created bootstrap admin: %s", settings.admin_email)
    finally:
        db.close()


def _ensure_commercial_board() -> None:
    db = SessionLocal()
    try:
        if db.query(CommercialBoard).count() == 0:
            db.add(
                CommercialBoard(
                    name="New IT Projects Pipeline",
                    description="Source, qualify and win new IT project opportunities.",
                )
            )
            db.commit()
            logger.info("Created default commercial board")
    finally:
        db.close()


def db_ready() -> bool:
    try:
        return inspect(engine).has_table("users")
    except Exception:
        return False
