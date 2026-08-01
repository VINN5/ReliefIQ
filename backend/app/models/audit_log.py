"""
Audit log model — a write-only, append-only record of security- and
compliance-relevant actions: sign-ins (success and failure), sign-ups,
document uploads/deletes, queries run, permission changes.

This table is intentionally never updated or deleted from application
code — only inserted into. Nothing in the service layer exposes an
update/delete path for it. If rows ever need to be removed, that's a
deliberate, manual DB operation (e.g. a retention policy job), not
something any API route should be able to trigger.

user_id is nullable because some actions worth logging happen before
we know who the user is — e.g. a failed sign-in with a bad email has
no resolvable User row to point at.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Nullable + SET NULL on delete: if a user account is ever deleted,
    # their historical audit trail should survive (that's the whole
    # point of an audit log) rather than cascading away with them.
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Denormalized snapshot of the org name at the time of the action.
    # There's no separate Organization table yet (User.organisation is
    # just a string) — once one exists, this can become a proper org_id
    # FK, but until then this keeps the "which org did this happen in"
    # question answerable without a join that doesn't exist.
    organisation: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Short machine-readable action code, e.g. "user.signup",
    # "user.signin_success", "user.signin_failed", "document.uploaded",
    # "document.deleted", "query.executed". Keep these dot-namespaced
    # and consistent — this is what you'll filter/group by later in the
    # analytics dashboard and admin audit log table.
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    # Optional pointer to whatever the action was about — a document id,
    # a target user id being modified, etc. Deliberately not a FK: the
    # referenced row's type varies by action, so this stays a plain UUID
    # and resource_type says what kind of thing it is.
    resource_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    resource_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )

    # Free-text context: the query string that was run, the email that
    # was attempted on a failed login, etc. Deliberately permissive —
    # different actions need different context, and forcing a rigid
    # schema per action type would slow this down for little benefit.
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)

    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )