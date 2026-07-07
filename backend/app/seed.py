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


def _ensure_column(table: str, column: str, ddl_type: str) -> None:
    """Add a column to an existing table if it's missing (MySQL & SQLite)."""
    try:
        insp = inspect(engine)
        if table not in insp.get_table_names():
            return  # create_all will build it fresh with the column present
        existing = {c["name"] for c in insp.get_columns(table)}
        if column not in existing:
            with engine.begin() as conn:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl_type}"))
            logger.info("Added column %s.%s", table, column)
    except Exception as exc:
        logger.warning("Could not ensure column %s.%s: %s", table, column, exc)


def _migrate_schema() -> None:
    """Bring an already-deployed database up to date without a migration tool."""
    # 1. Widen users.role ENUM -> VARCHAR and rename the legacy 'developer' role.
    if engine.dialect.name == "mysql":
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
                conn.execute(
                    text("UPDATE users SET role = 'dev' WHERE role = 'developer'")
                )
        except Exception as exc:  # never block startup on migration hiccups
            logger.warning("Role migration skipped: %s", exc)

    # 2. New columns added after the deliverables table already existed.
    _ensure_column("deliverables", "assignee_id", "INTEGER NULL")
    _ensure_column("deliverables", "completed", "INTEGER NOT NULL DEFAULT 0")

    # 3. File blob columns were first created as BLOB (64 KB cap). Widen to
    #    LONGBLOB so real documents fit. Idempotent; MySQL only.
    if engine.dialect.name == "mysql":
        insp = inspect(engine)
        tables = set(insp.get_table_names())
        for table in ("project_files", "deliverable_files"):
            if table not in tables:
                continue
            try:
                with engine.begin() as conn:
                    conn.execute(text(f"ALTER TABLE {table} MODIFY data LONGBLOB"))
                logger.info("Widened %s.data -> LONGBLOB", table)
            except Exception as exc:
                logger.warning("Could not widen %s.data: %s", table, exc)


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
