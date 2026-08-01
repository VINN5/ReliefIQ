"""
Pydantic schemas for the conversations API (chat sidebar + thread view).
"""

import uuid
from datetime import datetime

from pydantic import BaseModel

from app.schemas.query import Citation, ConfidenceLevel


class ConversationSummary(BaseModel):
    """One row in the sidebar list."""
    id: uuid.UUID
    title: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ConversationMessage(BaseModel):
    """One question/answer turn within a conversation thread."""
    id: uuid.UUID
    question: str
    answer: str
    confidence: ConfidenceLevel
    provider_used: str | None
    citations: list[Citation]
    needs_escalation: bool
    escalation_reason: str | None
    escalation_contacts: list[str]
    created_at: datetime

    model_config = {"from_attributes": True}