"""
Ingestion worker — orchestrates the pipeline stages for a single
document. It does NOT know how extraction/chunking/embedding actually
work internally; it just calls each service in order and updates status.

Runs as a FastAPI BackgroundTask, so it must open its own DB session —
the request's session is already closed by the time this runs.
"""

import logging
import uuid

from app.database import SessionLocal
from app.models.chunk import DocumentChunk
from app.models.document import Document, DocumentStatus
from app.services import chunking_service, embedding_service, extraction_service

logger = logging.getLogger(__name__)


def process_document(document_id: uuid.UUID) -> None:
    db = SessionLocal()
    try:
        document = db.get(Document, document_id)
        if document is None:
            logger.warning("process_document: document %s not found", document_id)
            return

        try:
            document.status = DocumentStatus.EXTRACTING.value
            db.commit()

            pages = extraction_service.extract(document.file_path, document.doc_type)

            if extraction_service.is_extraction_empty(pages):
                document.status = DocumentStatus.REQUIRES_OCR.value
                db.commit()
                return

            document.extracted_pages = [
                {"page": p.page_number, "text": p.text} for p in pages
            ]
            document.status = DocumentStatus.EXTRACTED.value
            db.commit()

            document.status = DocumentStatus.CHUNKING.value
            db.commit()

            db.query(DocumentChunk).filter(
                DocumentChunk.document_id == document.id
            ).delete()

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

            document.status = DocumentStatus.EMBEDDING.value
            db.commit()

            embeddings = embedding_service.embed_texts(
                [row.content for row in chunk_rows]
            )
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