"""
SpreadsheetTable model — one row per sheet (xlsx) or file (csv) parsed
from a spreadsheet Document. Stores the FULL structured data (headers +
rows, as JSONB) separately from DocumentChunk, which only holds a
capped, embeddable text rendering for retrieval.

Why separate from DocumentChunk: a chunk's content is what an LLM
reads — it has to stay small and text-shaped. The full row data here
is what the comparison tool (and, eventually, any programmatic
query engine) operates on directly, without size limits or lossy
text rendering. Same document, two different representations for two
different consumers.

Deliberately nested under Document (not a standalone table) so it
inherits everything Document already has for free: versioning
(supersedes_id/is_superseded), access_level (RBAC), and the audit
trail — no new permission model needed for spreadsheets.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SpreadsheetTable(Base):
    __tablename__ = "spreadsheet_tables"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sheet_name: Mapped[str] = mapped_column(String(255), nullable=False)

    # ["Programme", "Allocated", "Spent", ...]
    headers: Mapped[list] = mapped_column(JSONB, nullable=False)
    # [["WASH", 50000, 42000], ["Nutrition", 30000, 31500], ...] — each
    # inner list aligned to `headers` by position. JSON-safe values
    # only (dates stored as ISO strings, no Decimal/native date objects).
    rows: Mapped[list] = mapped_column(JSONB, nullable=False)

    row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )