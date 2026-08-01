"""
Conflict detection service — for a chosen document, finds internal
policy chunks elsewhere in the corpus that are topically related, and
asks an LLM whether they give staff contradictory guidance.

Pipeline per analysis:
  1. Take the target document's chunks (capped — see MAX_CHUNKS_TO_CHECK).
  2. For each chunk, find similar chunks from OTHER, non-superseded
     documents (retrieval_service.find_similar_chunks_from_other_documents)
     — only topically-related pairs are worth comparing at all.
  3. For each such pair, classify NO_CONFLICT / POTENTIAL_CONFLICT via
     generation_service.assess_conflict().
  4. Collect flagged pairs into a report; summarize with plain counts,
     same "don't spend an LLM call on the summary" philosophy as
     gap_detection_service.
"""

import logging
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.models.chunk import DocumentChunk
from app.models.document import Document
from app.services.generation_service import ConflictStatus, assess_conflict
from app.services.retrieval_service import find_similar_chunks_from_other_documents

logger = logging.getLogger(__name__)

MAX_CHUNKS_TO_CHECK = 20
CANDIDATES_PER_CHUNK = 2


@dataclass
class ConflictItem:
    target_excerpt: str
    target_page: int | None
    other_document_title: str
    other_excerpt: str
    other_page: int | None
    confidence: int
    explanation: str


@dataclass
class ConflictAnalysisResult:
    document_title: str
    items: list[ConflictItem] = field(default_factory=list)
    chunks_checked: int = 0
    comparisons_made: int = 0
    potential_conflicts_count: int = 0
    truncated: bool = False
    summary: str = ""


def _build_summary(
    document_title: str, conflicts: int, comparisons: int, chunks_checked: int, truncated: bool
) -> str:
    if chunks_checked == 0:
        return f"'{document_title}' has no chunks to analyze yet — it may still be processing."

    parts = [
        f"Compared {chunks_checked} section{'s' if chunks_checked != 1 else ''} of "
        f"'{document_title}' against related content in {comparisons} other "
        f"excerpt{'s' if comparisons != 1 else ''} across the knowledge base."
    ]
    if conflicts > 0:
        parts.append(
            f"{conflicts} potential conflict{'s' if conflicts != 1 else ''} found — review below."
        )
    else:
        parts.append("No potential conflicts found.")
    if truncated:
        parts.append(
            f"Only the first {MAX_CHUNKS_TO_CHECK} sections were checked; "
            "this document has more than this tool analyzes in one pass."
        )
    return " ".join(parts)


def analyze_document_conflicts(db: Session, document_id) -> ConflictAnalysisResult:
    target_document = db.query(Document).filter(Document.id == document_id).first()
    if target_document is None:
        raise ValueError("Document not found.")
    if target_document.is_superseded:
        raise ValueError(
            "This document has been superseded by a newer version — analyze the current version instead."
        )

    all_chunks = (
        db.query(DocumentChunk)
        .filter(DocumentChunk.document_id == target_document.id)
        .order_by(DocumentChunk.chunk_index)
        .all()
    )
    truncated = len(all_chunks) > MAX_CHUNKS_TO_CHECK
    target_chunks = all_chunks[:MAX_CHUNKS_TO_CHECK]

    items: list[ConflictItem] = []
    comparisons_made = 0

    for target_chunk in target_chunks:
        candidates = find_similar_chunks_from_other_documents(
            db, target_chunk, top_k=CANDIDATES_PER_CHUNK
        )

        for candidate in candidates:
            comparisons_made += 1
            assessment = assess_conflict(
                target_chunk.content,
                target_document.title,
                candidate.content,
                candidate.document_title,
            )

            if assessment.status == ConflictStatus.POTENTIAL_CONFLICT:
                items.append(
                    ConflictItem(
                        target_excerpt=target_chunk.content,
                        target_page=target_chunk.page_number,
                        other_document_title=candidate.document_title,
                        other_excerpt=candidate.content,
                        other_page=candidate.page_number,
                        confidence=assessment.confidence,
                        explanation=assessment.explanation,
                    )
                )

    # Highest-confidence findings first — the most clear-cut conflicts
    # are what a reviewer should see first, not just discovery order.
    items.sort(key=lambda i: i.confidence, reverse=True)

    summary = _build_summary(
        target_document.title, len(items), comparisons_made, len(target_chunks), truncated
    )

    return ConflictAnalysisResult(
        document_title=target_document.title,
        items=items,
        chunks_checked=len(target_chunks),
        comparisons_made=comparisons_made,
        potential_conflicts_count=len(items),
        truncated=truncated,
        summary=summary,
    )