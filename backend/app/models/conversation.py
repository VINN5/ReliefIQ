"""
Conversation model — groups a sequence of question/answer turns
together, the way a ChatGPT thread does, so the frontend can show a
sidebar of past conversations and let the user continue one instead of
every question being a disconnected, standalone entry.

title is auto-set from the first question in the conversation (see
query.py) and truncated — same pattern ChatGPT uses, no separate
"name your chat" step required from the user.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

TITLE_MAX_LENGTH = 80


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(TITLE_MAX_LENGTH), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    # Bumped every time a new message is added — lets the sidebar sort
    # by "most recently active" rather than "first created", matching
    # how ChatGPT's sidebar reorders a conversation to the top the
    # moment you send a new message in it.
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )