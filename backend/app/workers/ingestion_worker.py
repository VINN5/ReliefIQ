"""
Ingestion worker — orchestrates the pipeline stages for a single
document. It does NOT know how extraction/chunking/embedding actually
work internally; it just calls each service in order and updates status.

Branches on doc_type early: spreadsheets (.xlsx/.csv) go through a
structurally different path than prose documents (.pdf/.docx) — see
_process_spreadsheet vs _process_prose_document. Both converge back to
the same DocumentChunk + embedding + READY flow, so retrieval doesn't
need to know which path a document took.

Runs as a FastAPI BackgroundTask, so it must open its own DB session —
the request's session is already closed by the time this runs.
"""

import logging
import uuid

from app.database import SessionLocal
from app.models.chunk import DocumentChunk
from app.models.document import Document, DocumentStatus
from app.models.spreadsheet_table import SpreadsheetTable
from app.services import chunking_service, embedding_service, extraction_service, spreadsheet_service
from app.services.content_safety import strip_prompt_injection

logger = logging.getLogger(__name__)

_SPREADSHEET_TYPES = {"xlsx", "csv"}


def process_document(document_id: uuid.UUID) -> None:
    db = SessionLocal()
    try:
        document = db.get(Document, document_id)
        if document is None:
            logger.warning("process_document: document %s not found", document_id)
            return

        try:
            if document.doc_type in _SPREADSHEET_TYPES:
                chunk_rows = _process_spreadsheet(db, document)
            else:
                chunk_rows = _process_prose_document(db, document)

            if chunk_rows is None:
                # _process_prose_document signals REQUIRES_OCR by
                # returning None — status is already set, nothing more
                # to do here.
                return

            document.status = DocumentStatus.EMBEDDING.value
            db.commit()

            embeddings = embedding_service.embed_texts([row.content for row in chunk_rows])
            for row, vector in zip(chunk_rows, embeddings):
                row.embedding = vector
            db.commit()

            document.status = DocumentStatus.READY.value
            db.commit()

        except Exception:
            logger.exception("Ingestion pipeline failed for document %s", document_id)
            document.status = DocumentStatus.FAILED.value
            db.commit()

    finally:
        db.close()


def _process_prose_document(db, document: Document) -> list[DocumentChunk] | None:
    """Original PDF/DOCX path — extraction -> chunking. Unchanged behavior."""
    document.status = DocumentStatus.EXTRACTING.value
    db.commit()

    pages = extraction_service.extract(document.file_path, document.doc_type)

    if extraction_service.is_extraction_empty(pages):
        document.status = DocumentStatus.REQUIRES_OCR.value
        db.commit()
        return None

    document.extracted_pages = [{"page": p.page_number, "text": p.text} for p in pages]
    document.status = DocumentStatus.EXTRACTED.value
    db.commit()

    document.status = DocumentStatus.CHUNKING.value
    db.commit()

    db.query(DocumentChunk).filter(DocumentChunk.document_id == document.id).delete()

    chunks = chunking_service.chunk_pages(document.extracted_pages)
    chunk_rows = [
        DocumentChunk(
            document_id=document.id,
            chunk_index=index,
            content=chunk.content,
            page_number=chunk.page_number,
            section_heading=chunk.section_heading,
        )
        for index, chunk in enumerate(chunks)
    ]
    db.add_all(chunk_rows)
    document.status = DocumentStatus.CHUNKED.value
    db.commit()
    return chunk_rows


def _process_spreadsheet(db, document: Document) -> list[DocumentChunk]:
    """
    Spreadsheet path — parse into structured tables (stored in full in
    SpreadsheetTable), then create ONE retrieval chunk per sheet, using
    a capped markdown rendering as its content. See
    spreadsheet_service.py for why the full data and the chunk content
    are kept separate.
    """
    document.status = DocumentStatus.EXTRACTING.value
    db.commit()

    with open(document.file_path, "rb") as f:
        file_bytes = f.read()

    tables = spreadsheet_service.parse_spreadsheet(file_bytes, document.doc_type, document.title)

    if not tables:
        # An empty/unreadable spreadsheet is the tabular equivalent of
        # a PDF needing OCR — nothing usable was extracted.
        document.status = DocumentStatus.REQUIRES_OCR.value
        db.commit()
        return None

    document.status = DocumentStatus.EXTRACTED.value
    db.commit()

    document.status = DocumentStatus.CHUNKING.value
    db.commit()

    db.query(SpreadsheetTable).filter(SpreadsheetTable.document_id == document.id).delete()
    db.query(DocumentChunk).filter(DocumentChunk.document_id == document.id).delete()

    chunk_rows = []
    for index, table in enumerate(tables):
        db.add(
            SpreadsheetTable(
                document_id=document.id,
                sheet_name=table.sheet_name,
                headers=table.headers,
                rows=table.rows,
                row_count=len(table.rows),
            )
        )

        raw_content = spreadsheet_service.render_table_markdown(table)
        safe_content = strip_prompt_injection(raw_content, source="ingestion")

        chunk_rows.append(
            DocumentChunk(
                document_id=document.id,
                chunk_index=index,
                content=safe_content,
                page_number=None,
                section_heading=table.sheet_name,
            )
        )

    db.add_all(chunk_rows)
    document.status = DocumentStatus.CHUNKED.value
    db.commit()
    return chunk_rows