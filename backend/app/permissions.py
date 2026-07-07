"""Role groups used across routers.

`admin` (super admin) is included in every group, so it always has access.
"""
from app.models import UserRole

# Individual roles with elevated scope
DEV_ADMINS = {UserRole.admin, UserRole.admin_dev}
COMMERCIAL_ADMINS = {UserRole.admin, UserRole.admin_comercial}
ALL_ADMINS = {UserRole.admin, UserRole.admin_dev, UserRole.admin_comercial}

# Team membership (admins of that team included)
DEV_TEAM = {UserRole.admin, UserRole.admin_dev, UserRole.dev}
COMMERCIAL_TEAM = {UserRole.admin, UserRole.admin_comercial, UserRole.comercial}


def role_values(roles) -> set[str]:
    return {r.value if isinstance(r, UserRole) else str(r) for r in roles}
