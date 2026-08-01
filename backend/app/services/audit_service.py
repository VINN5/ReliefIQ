"""
Audit logging service.

One function, log_action(), is the only way anything in the app writes
to audit_logs. Keeping it centralized here — rather than letting every
route construct AuditLog rows itself — means the write path, error
handling, and field conventions stay consistent no matter which
endpoint is logging.

Deliberate design choice: a failure to write an audit log must never
break the request that triggered it. Losing an audit entry is bad;
failing someone's sign-in because the audit table had a hiccup would
be worse. So log_action() swallows its own exceptions after logging
them, rather than propagating.
"""

import logging
import uuid

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.user import User

logger = logging.getLogger(__name__)


def log_action(
    db: Session,
    *,
    action: str,
    user: User | None = None,
    resource_type: str | None = None,
    resource_id: uuid.UUID | None = None,
    detail: str | None = None,
    ip_address: str | None = None,
) -> None:
    """
    Write one audit log entry.

    `user` is optional — pass None for actions where no user could be
    resolved (e.g. a failed sign-in against an email that doesn't
    exist). `action` should be a short dot-namespaced code, e.g.
    "user.signin_success" — see audit_log.py for the convention.

    Commits independently of whatever transaction the caller is in.
    This is deliberate: audit entries should persist even if you later
    decide to log an action and then roll back unrelated work in the
    same request — the audit trail isn't supposed to be conditional on
    the outcome of business logic.
    """
    try:
        entry = AuditLog(
            user_id=user.id if user else None,
            organisation=user.organisation if user else None,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            detail=detail,
            ip_address=ip_address,
        )
        db.add(entry)
        db.commit()
    except Exception:
        # Never let an audit-logging failure surface as a request
        # failure. Roll back just the audit insert so it can't leave
        # the session in a broken state for whatever the caller does
        # next, and log loudly so this doesn't fail silently forever.
        db.rollback()
        logger.exception("Failed to write audit log entry for action '%s'", action)


def client_ip(request) -> str | None:
    """
    Best-effort extraction of the caller's IP from a FastAPI Request.
    Small helper so every call site doesn't repeat the same fallback
    logic — request.client is None in some test/proxy setups.
    """
    if request is None or request.client is None:
        return None
    return request.client.host