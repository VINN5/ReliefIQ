"""
Pydantic schemas for the admin audit log viewer.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel


class AuditLogEntry(BaseModel):
    id: uuid.UUID
    action: str
    user_id: uuid.UUID | None
    user_email: str | None
    organisation: str | None
    resource_type: str | None
    resource_id: uuid.UUID | None
    detail: str | None
    ip_address: str | None
    created_at: datetime


class AuditLogPage(BaseModel):
    items: list[AuditLogEntry]
    total: int
    limit: int
    offset: int