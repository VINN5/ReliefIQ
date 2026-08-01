"""
Retrieval service — given a natural-language question, finds the most
semantically similar chunks already stored in the database.

No LLM involved here. This is the "does retrieval actually work"
milestone — proving the right content surfaces before any generation
is layered on top.

Distance metric: cosine, matching how chunk embeddings were created
(normalize_embeddings=True in embedding_service.py). pgvector's `<=>`
operator returns cosine DISTANCE (0 = identical, 2 = opposite), so we
convert it to a more intuitive similarity score (1 = identical, -1 =
opposite) for the API response.

Confidence thresholds below are derived from real measured scores
against this project's own corpus, not arbitrary guesses:
  - genuinely relevant matches:      ~0.45-0.70
  - topically related but shaky:     ~0.30-0.45
  - unrelated / out-of-scope:        ~0.14-0.22

Access control: retrieval is filtered by the requesting user's role
before ranking/limiting. RESTRICTED documents (e.g. safeguarding
policies) are excluded entirely from field_staff results — not just
flagged afterward — so a restricted chunk can never appear in a
field_staff citation, confidence score, or generated answer. This
mirrors the document-library restriction in documents.py rather than
introducing a separate access model.
"""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.chunk import DocumentChunk
from app.models.document import Document, DocumentAccessLevel
from app.models.user import UserRole
from app.schemas.query import ConfidenceLevel
from app.services.embedding_service import embed_texts

HIGH_CONFIDENCE_THRESHOLD = 0.45
MEDIUM_CONFIDENCE_THRESHOLD = 0.30

# Roles allowed to retrieve RESTRICTED documents. Kept as one constant
# so this can't drift out of sync with the DOCUMENT_MANAGER_ROLES-style
# checks elsewhere (documents.py, Dashboard.tsx).
_ROLES_WITH_RESTRICTED_ACCESS = {UserRole.MANAGER.value, UserRole.ADMIN.value}


@dataclass
class RetrievedChunk:
    chunk_id: UUID
    document_id: UUID
    document_title: str
    content: str
    page_number: int | None
    section_heading: str | None
    similarity: float


def search_similar_chunks(
    db: Session,
    question: str,
    top_k: int = 5,
    requester_role: str | None = None,
) -> list[RetrievedChunk]:
    """
    Embeds `question` and returns the top_k most similar chunks the
    requester is allowed to see, ranked by cosine similarity (highest
    first).

    `requester_role` gates access to RESTRICTED documents (see
    DocumentAccessLevel). Passing None is treated as the most
    restrictive case — no restricted content is returned — rather than
    defaulting open, so a caller that forgets to pass a role fails
    closed, not open.
    """
    query_embedding = embed_texts([question])[0]

    distance = DocumentChunk.embedding.cosine_distance(query_embedding)

    stmt = (
        select(DocumentChunk, Document.title, distance.label("distance"))
        .join(Document, DocumentChunk.document_id == Document.id)
        .where(DocumentChunk.embedding.is_not(None))
        # Superseded versions are excluded for EVERYONE, not just
        # gated by role — an outdated policy shouldn't ground an
        # answer just because it's technically still readable by an
        # admin. Old versions remain in the table (and in the document
        # library / audit trail) for history; they just never surface
        # in Q&A once replaced.
        .where(Document.is_superseded.is_(False))
    )

    if requester_role not in _ROLES_WITH_RESTRICTED_ACCESS:
        stmt = stmt.where(Document.access_level != DocumentAccessLevel.RESTRICTED.value)

    stmt = stmt.order_by(distance).limit(top_k)

    results = db.execute(stmt).all()

    return [
        RetrievedChunk(
            chunk_id=chunk.id,
            document_id=chunk.document_id,
            document_title=title,
            content=chunk.content,
            page_number=chunk.page_number,
            section_heading=chunk.section_heading,
            similarity=1 - dist,
        )
        for chunk, title, dist in results
    ]


def compute_confidence(chunks: list[RetrievedChunk]) -> ConfidenceLevel:
    """
    Confidence is based on the single BEST match, not an average —
    one genuinely relevant chunk is enough to answer well, even if
    the other top_k results are weaker filler.
    """
    if not chunks:
        return ConfidenceLevel.LOW

    top_similarity = max(chunk.similarity for chunk in chunks)

    if top_similarity >= HIGH_CONFIDENCE_THRESHOLD:
        return ConfidenceLevel.HIGH
    if top_similarity >= MEDIUM_CONFIDENCE_THRESHOLD:
        return ConfidenceLevel.MEDIUM
    return ConfidenceLevel.LOW


def find_similar_chunks_from_other_documents(
    db: Session,
    source_chunk: DocumentChunk,
    top_k: int = 2,
    min_similarity: float = HIGH_CONFIDENCE_THRESHOLD,
) -> list[RetrievedChunk]:
    """
    Given a chunk, finds the most similar chunks belonging to DIFFERENT
    documents — used by conflict detection to find candidate pairs
    worth comparing. Reuses `source_chunk`'s already-computed embedding
    directly (pgvector distance against a stored vector) rather than
    re-embedding its text — cheaper, and avoids a redundant call to the
    embedding model for content that's already been embedded once.

    Superseded documents are excluded, same as normal retrieval — an
    outdated policy shouldn't get flagged as "conflicting" with a
    current one when it's not even in active use anymore.

    min_similarity filters out topically-unrelated matches: two chunks
    about completely different subjects can't meaningfully "conflict"
    with each other, so there's no point spending an LLM call on them.
    """
    if source_chunk.embedding is None:
        return []

    distance = DocumentChunk.embedding.cosine_distance(source_chunk.embedding)

    stmt = (
        select(DocumentChunk, Document.title, distance.label("distance"))
        .join(Document, DocumentChunk.document_id == Document.id)
        .where(DocumentChunk.embedding.is_not(None))
        .where(DocumentChunk.document_id != source_chunk.document_id)
        .where(Document.is_superseded.is_(False))
        .order_by(distance)
        .limit(top_k)
    )

    results = db.execute(stmt).all()

    candidates = [
        RetrievedChunk(
            chunk_id=chunk.id,
            document_id=chunk.document_id,
            document_title=title,
            content=chunk.content,
            page_number=chunk.page_number,
            section_heading=chunk.section_heading,
            similarity=1 - dist,
        )
        for chunk, title, dist in results
    ]

    return [c for c in candidates if c.similarity >= min_similarity]