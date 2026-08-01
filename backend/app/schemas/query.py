"""
Pydantic schemas for the query/retrieval API. Kept separate from the
SQLAlchemy models so the API's public shape can evolve independently
of the database schema.
"""

import enum
import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=20)
    # None = start a new conversation. Provided = continue that one.
    conversation_id: uuid.UUID | None = None


class RetrievedChunkResponse(BaseModel):
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_title: str
    content: str
    page_number: int | None
    section_heading: str | None
    similarity: float

    model_config = {"from_attributes": True}


class QueryResponse(BaseModel):
    question: str
    results: list[RetrievedChunkResponse]


class Citation(BaseModel):
    number: int
    document_title: str
    page_number: int | None


class ConfidenceLevel(str, enum.Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class AnswerResponse(BaseModel):
    question: str
    answer: str
    confidence: ConfidenceLevel
    citations: list[Citation]
    sources: list[RetrievedChunkResponse]
    # Which LLM provider actually generated this answer (e.g. "gemini",
    # "groq", "anthropic"). None when no chunks were retrieved and the
    # fixed "no information found" response was returned without calling
    # any provider — see generation_service.generate_answer.
    provider_used: str | None = None

    # --- Human escalation branch ---
    # True when this query should be routed to a human rather than
    # trusted as-is: low confidence, a rejected (uncited) generation,
    # or the question matching a sensitive category (safeguarding,
    # legal, etc). The frontend renders an EscalationPrompt when true.
    needs_escalation: bool = False
    escalation_reason: str | None = None
    escalation_contacts: list[str] = []

    conversation_id: uuid.UUID


class QueryHistoryItem(BaseModel):
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