"""
Document model — represents a single uploaded source file (policy, manual,
guideline, etc).

Versioning: uploading a "new version" of an existing document (see
POST /documents/{document_id}/replace) creates a NEW Document row
rather than mutating the old one in place — the old version stays
intact for audit/history purposes, just marked is_superseded=True and
excluded from retrieval going forward (see retrieval_service.py).
supersedes_id links a new version back to the one it replaces;
version is a simple incrementing counter for display (v1, v2, ...).
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class DocumentStatus(str, enum.Enum):
    UPLOADING = "uploading"
    EXTRACTING = "extracting"
    REQUIRES_OCR = "requires_ocr"
    EXTRACTED = "extracted"
    CHUNKING = "chunking"
    CHUNKED = "chunked"
    EMBEDDING = "embedding"
    INDEXING = "indexing"
    READY = "ready"
    FAILED = "failed"


class DocumentAccessLevel(str, enum.Enum):
    STANDARD = "standard"
    RESTRICTED = "restricted"


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    doc_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(
        String(50), nullable=False,
        default=DocumentStatus.UPLOADING.value,
        server_default=DocumentStatus.UPLOADING.value,
    )

    access_level: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=DocumentAccessLevel.STANDARD.value,
        server_default=DocumentAccessLevel.STANDARD.value,
    )

    # --- Versioning ---
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
    )
    # Denormalized flag rather than a live "does anything point at me"
    # subquery — set explicitly at replace time (see documents.py). Old
    # versions stay in the table (never deleted, for audit/history) but
    # are excluded from retrieval once superseded, so citations/answers
    # only ever ground in the current version of a policy.
    is_superseded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")

    extracted_pages: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    chunks: Mapped[list["DocumentChunk"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )