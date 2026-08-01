"""
User model — an individual account within an organisation using ReliefIQ.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class UserRole(str, enum.Enum):
    FIELD_STAFF = "field_staff"
    MANAGER = "manager"
    ADMIN = "admin"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    organisation: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    # New accounts default to the most restricted role. Promoting someone
    # to manager/admin is a deliberate act (currently: a manual DB update
    # or an admin endpoint later) — never something signup itself grants.
    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=UserRole.FIELD_STAFF.value,
        server_default=UserRole.FIELD_STAFF.value,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )