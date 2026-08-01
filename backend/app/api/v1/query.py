"""
Query API routes. Two endpoints, deliberately kept separate:

- POST /query        -> pure retrieval, no LLM. Useful for debugging
                         and inspecting what the system would ground
                         an answer in.
- POST /query/answer  -> full RAG: retrieval + grounded, cited answer,
                          with a confidence level based on match quality.
                          Also creates/continues a Conversation thread
                          (see conversations.py for the sidebar/thread
                          read endpoints) and persists the turn to
                          QueryHistory.

/query/answer also decides whether to escalate a query to a human
rather than let the user rely on the AI answer alone. Escalation
triggers on any of:
  - LOW confidence retrieval
  - the generation guardrail rejecting an uncited answer
  - the question matching a sensitive-category keyword (safeguarding,
    legal, etc) — these categories warrant a human regardless of how
    confident the retrieval looked, since the cost of a wrong answer
    is higher than usual.
This is pattern/keyword-based, not ML-based — same "scope it honestly"
philosophy as the prompt-injection stripping in generation_service.py.
It catches the obvious cases; it isn't a complete classifier.
"""

import logging
import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.v1.auth import get_current_user
from app.database import get_db
from app.models.conversation import TITLE_MAX_LENGTH, Conversation
from app.models.query_history import QueryHistory
from app.models.user import User
from app.schemas.query import (
    AnswerResponse,
    Citation,
    ConfidenceLevel,
    QueryHistoryItem,
    QueryRequest,
    QueryResponse,
)
from app.services.audit_service import client_ip, log_action
from app.services.generation_service import generate_answer
from app.services.retrieval_service import compute_confidence, search_similar_chunks

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/query", tags=["query"])

# Keyword groups mapped to who should be looped in. A question can match
# more than one group; contacts are deduplicated in the order matched.
# Keep this list conservative and easy to extend — it's meant to catch
# obviously sensitive topics, not to be a exhaustive taxonomy.
_SENSITIVE_CATEGORIES: dict[str, tuple[list[str], list[str]]] = {
    "safeguarding": (
        ["safeguard", "abuse", "exploitation", "child protection", "sexual harassment", "sgbv"],
        ["Safeguarding Officer"],
    ),
    "legal": (
        ["legal", "lawsuit", "liability", "compliance violation", "contract dispute"],
        ["Legal"],
    ),
    "hr": (
        ["disciplinary", "termination", "grievance", "harassment complaint"],
        ["HR"],
    ),
}


def _match_sensitive_categories(question: str) -> tuple[bool, list[str]]:
    """
    Returns (matched, contacts). Case-insensitive substring match against
    each category's keyword list — deliberately simple; false positives
    (routing an unrelated "legal" mention to Legal) are an acceptable
    cost given the alternative is silently under-escalating something
    that actually needed a human.
    """
    question_lower = question.lower()
    contacts: list[str] = []
    matched = False
    for _category, (keywords, category_contacts) in _SENSITIVE_CATEGORIES.items():
        # \b before the keyword only — not after. A trailing \b would
        # require an exact word match, so "safeguard" wouldn't match
        # inside "safeguarding" (no boundary between "safeguard" and
        # "ing", both are word characters). Matching common word forms
        # like this is the whole point of a keyword-based check.
        if any(re.search(rf"\b{re.escape(kw)}", question_lower) for kw in keywords):
            matched = True
            for contact in category_contacts:
                if contact not in contacts:
                    contacts.append(contact)
    return matched, contacts


def _make_title(question: str) -> str:
    """Truncates the first question into a conversation title, ChatGPT-style."""
    question = question.strip()
    if len(question) <= TITLE_MAX_LENGTH:
        return question
    return question[: TITLE_MAX_LENGTH - 1].rstrip() + "…"


@router.post("", response_model=QueryResponse)
def run_query(
    request: Request,
    payload: QueryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    results = search_similar_chunks(
        db, payload.question, top_k=payload.top_k, requester_role=current_user.role
    )

    log_action(
        db,
        action="query.retrieval_run",
        user=current_user,
        detail=payload.question,
        ip_address=client_ip(request),
    )

    return QueryResponse(question=payload.question, results=results)


@router.post("/answer", response_model=AnswerResponse)
def answer_query(
    request: Request,
    payload: QueryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # --- Resolve which conversation this turn belongs to ---
    # No conversation_id in the request -> this is the first message of
    # a new chat, so create one now (title from this question). An id
    # that IS provided must belong to the caller — 404 rather than 403
    # if it doesn't, same reasoning as conversations.py: don't confirm
    # a conversation ID exists at all if it isn't the caller's.
    if payload.conversation_id is None:
        conversation = Conversation(user_id=current_user.id, title=_make_title(payload.question))
        db.add(conversation)
        db.flush()  # assigns conversation.id without committing yet
    else:
        conversation = (
            db.query(Conversation)
            .filter(
                Conversation.id == payload.conversation_id,
                Conversation.user_id == current_user.id,
            )
            .first()
        )
        if conversation is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found."
            )

    chunks = search_similar_chunks(
        db, payload.question, top_k=payload.top_k, requester_role=current_user.role
    )
    confidence = compute_confidence(chunks)

    # generate_answer() raises a plain RuntimeError if every configured
    # provider (Gemini, Groq, Anthropic, ...) fails on this request —
    # a real event, not hypothetical: this has already happened once in
    # this project (Gemini blocked, Groq VPN-blocked, Anthropic out of
    # credits, all at the same time). Left uncaught, FastAPI turns that
    # into a raw 500 with a stack trace as the response body — accurate
    # for a developer reading logs, useless and alarming for a user
    # reading it in the UI. Catch it here and translate it into a clean,
    # honest 503 instead: "temporarily unavailable" is the true story,
    # and it's also the one signal that tells the frontend to show a
    # retry-friendly message rather than treating this like a bug.
    try:
        generated = generate_answer(payload.question, chunks)
    except RuntimeError:
        logger.exception(
            "All generation providers failed for user %s on question: %s",
            current_user.id,
            payload.question,
        )
        log_action(
            db,
            action="query.provider_outage",
            user=current_user,
            detail=f"question: {payload.question} | all providers failed",
            ip_address=client_ip(request),
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Our AI providers are temporarily unavailable. "
                "Please try again in a few minutes."
            ),
        )

    citations = [
        Citation(
            number=i,
            document_title=chunk.document_title,
            page_number=chunk.page_number,
        )
        for i, chunk in enumerate(chunks, start=1)
    ]

    # --- Escalation decision ---
    sensitive_matched, sensitive_contacts = _match_sensitive_categories(payload.question)

    needs_escalation = (
        confidence == ConfidenceLevel.LOW
        or generated.grounding_rejected
        or sensitive_matched
    )

    escalation_reason: str | None = None
    escalation_contacts: list[str] = []

    if needs_escalation:
        if generated.grounding_rejected:
            escalation_reason = (
                "The system couldn't produce a verified, cited answer for this question."
            )
            escalation_contacts = ["Program Manager"]
        elif sensitive_matched:
            escalation_reason = (
                "This question touches a sensitive category that should be reviewed by a person."
            )
            escalation_contacts = sensitive_contacts
        else:
            escalation_reason = (
                "The available documents only weakly match this question — verify before acting."
            )
            escalation_contacts = ["Program Manager"]

    log_action(
        db,
        action="query.executed",
        user=current_user,
        detail=(
            f"question: {payload.question} | provider: {generated.provider_used} | "
            f"confidence: {confidence.value} | needs_escalation: {needs_escalation}"
        ),
        ip_address=client_ip(request),
    )

    # Persist the turn AND bump the conversation's updated_at (so it
    # sorts to the top of the sidebar) in one transaction. A failure
    # here shouldn't break the response the user is about to receive —
    # same "don't let persistence break the real feature" philosophy as
    # audit_service.log_action().
    try:
        history_entry = QueryHistory(
            user_id=current_user.id,
            conversation_id=conversation.id,
            question=payload.question,
            answer=generated.answer_text,
            confidence=confidence.value,
            provider_used=generated.provider_used,
            citations=[c.model_dump() for c in citations],
            needs_escalation=needs_escalation,
            escalation_reason=escalation_reason,
            escalation_contacts=escalation_contacts,
        )
        db.add(history_entry)
        conversation.updated_at = datetime.now(timezone.utc)
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Failed to persist query history for user %s", current_user.id)

    return AnswerResponse(
        question=payload.question,
        answer=generated.answer_text,
        confidence=confidence,
        citations=citations,
        sources=chunks,
        provider_used=generated.provider_used,
        needs_escalation=needs_escalation,
        escalation_reason=escalation_reason,
        escalation_contacts=escalation_contacts,
        conversation_id=conversation.id,
    )


@router.get("/history", response_model=list[QueryHistoryItem])
def get_query_history(
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Flat, ungrouped list of the current user's past turns — superseded
    by GET /conversations for the chat UI, kept around as a simple
    fallback/debug view since it's cheap to maintain.
    """
    limit = max(1, min(limit, 100))
    return (
        db.query(QueryHistory)
        .filter(QueryHistory.user_id == current_user.id)
        .order_by(QueryHistory.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )