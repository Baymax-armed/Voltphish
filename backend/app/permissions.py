"""Granular RBAC on top of the base admin/operator roles (CLAUDE.md A01).

Admins implicitly hold every permission. Operators hold none of the delegated
"admin area" permissions by default, but an admin can grant specific ones
(stored on User.extra_permissions as a CSV) — e.g. make an operator a delegated
user-manager without giving them full admin. Fail closed: unknown ⇒ denied.
"""
from __future__ import annotations

from fastapi import Depends, HTTPException, status

from .dependencies import get_current_user
from .models import User, UserRole

# Catalog of delegatable permissions (admin-area capabilities).
PERMISSIONS: dict[str, str] = {
    "users:manage": "Create, edit, and remove user accounts",
    "settings:manage": "Configure AI, SSO, IMAP, and other settings",
    "webhooks:manage": "Manage outbound webhooks",
    "training:manage": "Create and assign training modules",
    "reported:view": "View and triage reported emails",
}


def permissions_for(user: User) -> list[str]:
    """Effective permission keys for a user (admins get everything)."""
    if user.role is UserRole.admin:
        return list(PERMISSIONS.keys())
    return [p.strip() for p in (user.extra_permissions or "").split(",") if p.strip() in PERMISSIONS]


def has_permission(user: User, perm: str) -> bool:
    return user.role is UserRole.admin or perm in permissions_for(user)


def sanitize_permissions(raw: list[str] | None) -> str | None:
    """Filter to known keys and serialize to CSV for storage."""
    if not raw:
        return None
    keep = [p for p in dict.fromkeys(raw) if p in PERMISSIONS]  # dedupe, keep order
    return ",".join(keep) or None


def require_permission(perm: str):
    """Dependency factory: allow admins, or non-admins holding `perm`."""

    def _dep(user: User = Depends(get_current_user)) -> User:
        if not has_permission(user, perm):
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail="You don't have permission for this action")
        return user

    return _dep
