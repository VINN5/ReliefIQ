"""
Admin audit log viewer — replaces the "run a Python one-liner in the
terminal" approach that's been the only way to inspect audit_logs so
far. Admin-only: audit logs contain other users' activity, IP
addresses, and org-wide data, which is a materially more sensitive
surface than the manager-level document/gap-detection tools — hence
the tighter restriction here than elsewhere in the app.

Supports basic filtering (by action, by user email substring) and
pagination — the audit_logs table only grows, so an unpaginated
"return everything" endpoint would get slower and heavier every day
the app is used.
"""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.v1.auth import require_role
from app.database import get_db
from app.models.audit_log import AuditLog
from app.models.user import User, UserRole
from app.schemas.audit_log import AuditLogEntry, AuditLogPage

router = APIRouter(prefix="/admin/audit-logs", tags=["admin"])


@router.get("", response_model=AuditLogPage)
def list_audit_logs(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    action: str | None = Query(default=None, description="Exact action code, e.g. 'user.signin_failed'"),
    user_email: str | None = Query(default=None, description="Case-insensitive substring match"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    query = db.query(AuditLog, User.email).outerjoin(User, AuditLog.user_id == User.id)

    if action:
        query = query.filter(AuditLog.action == action)
    if user_email:
        query = query.filter(User.email.ilike(f"%{user_email}%"))

    total = query.with_entities(func.count()).order_by(None).scalar() or 0

    rows = (
        query.order_by(AuditLog.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    items = [
        AuditLogEntry(
            id=log.id,
            action=log.action,
            user_id=log.user_id,
            user_email=email,
            organisation=log.organisation,
            resource_type=log.resource_type,
            resource_id=log.resource_id,
            detail=log.detail,
            ip_address=log.ip_address,
            created_at=log.created_at,
        )
        for log, email in rows
    ]

    return AuditLogPage(items=items, total=total, limit=limit, offset=offset)


@router.get("/actions", response_model=list[str])
def list_distinct_actions(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """
    Distinct action codes seen so far — powers a filter dropdown in the
    UI instead of making the admin guess/type exact action strings like
    'user.signin_failed' from memory.
    """
    rows = db.query(AuditLog.action).distinct().order_by(AuditLog.action).all()
    return [r[0] for r in rows]