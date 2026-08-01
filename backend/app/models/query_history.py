"""
QueryHistory model — persists each answered question/turn so a user
can revisit a conversation across sessions.

conversation_id groups turns into a thread (see conversation.py) —
nullable because rows created before conversations existed won't have
one; new rows always get one (query.py creates a Conversation
automatically on a user's first message if none was specified).

Deliberately separate from audit_logs: audit_logs is a compliance/
security trail the app never lets users browse as "my history" — this
table is what actually powers the chat UI. Uses CASCADE (not SET NULL
like audit_logs) since there's no compliance reason to keep a user's
personal chat history after their account is deleted.

Only populated by POST /query/answer (the full RAG endpoint) — the
debug-only POST /query (raw retrieval, no LLM) never writes here.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class QueryHistory(Base):
    __tablename__ = "query_history"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=True, index=True
    )

    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[str] = mapped_column(String(20), nullable=False)
    provider_used: Mapped[str | None] = mapped_column(String(50), nullable=True)

    citations: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    needs_escalation: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    escalation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    escalation_contacts: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )