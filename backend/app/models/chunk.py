"""
DocumentChunk model — a retrievable slice of a Document's text, with
enough metadata (page, section, order) to produce a real citation later.

embedding: a 384-dimension vector, matching the output size of the
all-MiniLM-L6-v2 sentence-transformers model. If the embedding model
ever changes to one with a different output size, this column's
dimension must be updated via a new migration, and all existing
embeddings regenerated — dimensions can't be mixed in one column.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from pgvector.sqlalchemy import Vector
from sqlalchemy import String, Text, Integer, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    # Only imported for type checkers (Pylance) — at runtime this would
    # be a circular import, since document.py imports DocumentChunk
    # back. The string forward reference "Document" in the
    # relationship() below already works fine at runtime; this just
    # lets Pylance resolve it too instead of flagging
    # reportUndefinedVariable.
    from app.models.document import Document

EMBEDDING_DIMENSIONS = 384


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    section_heading: Mapped[str | None] = mapped_column(String(255), nullable=True)
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(EMBEDDING_DIMENSIONS), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    document: Mapped["Document"] = relationship(back_populates="chunks")