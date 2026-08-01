"""
Ingestion service — handles everything about getting an uploaded file
safely onto disk. Text extraction and chunking are separate services,
added in later steps of the ingestion pipeline.
"""

import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile

from app.config import settings

ALLOWED_EXTENSIONS = {".pdf", ".docx"}


def validate_file(file: UploadFile) -> str:
    """
    Confirms the uploaded file has an allowed extension.
    Returns the lowercase extension (e.g. ".pdf") for reuse by the caller.
    Raises HTTPException(400) if invalid.
    """
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{suffix}'. Allowed: {sorted(ALLOWED_EXTENSIONS)}",
        )
    return suffix


def save_file(file: UploadFile, document_id: uuid.UUID, suffix: str) -> str:
    """
    Streams the uploaded file to disk in chunks (so large PDFs don't get
    fully buffered in memory), enforcing the max size limit as it goes.
    Returns the path the file was saved to.
    """
    storage_dir = Path(settings.storage_dir)
    storage_dir.mkdir(parents=True, exist_ok=True)

    destination = storage_dir / f"{document_id}{suffix}"
    max_bytes = settings.max_upload_size_mb * 1024 * 1024

    size = 0
    exceeded = False

    with destination.open("wb") as out_file:
        while chunk := file.file.read(1024 * 1024):
            size += len(chunk)
            if size > max_bytes:
                # Stop writing and fall out of the `with` block instead
                # of unlinking here. Deleting `destination` WHILE
                # `out_file` (the same path) is still open fails on
                # Windows with WinError 32 ("used by another process") —
                # Windows, unlike POSIX, won't let a process delete a
                # file it currently has open itself. That crash used to
                # mask the real, correct "file too large" error below.
                exceeded = True
                break
            out_file.write(chunk)

    if exceeded:
        # Safe to delete now — the `with` block above has already
        # closed the file handle before we get here.
        destination.unlink(missing_ok=True)
        raise HTTPException(
            status_code=400,
            detail=f"File exceeds max size of {settings.max_upload_size_mb}MB",
        )

    return str(destination)