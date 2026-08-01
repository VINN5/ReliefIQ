"""
Document API routes. Route handlers stay thin — validation and file
handling live in the ingestion service; the actual processing pipeline
lives in the ingestion worker, run as a background task.
"""

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, Request, UploadFile, File, status
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.api.v1.auth import require_role
from app.database import get_db
from app.models.document import Document, DocumentAccessLevel, DocumentStatus
from app.models.user import User, UserRole
from app.schemas.document import DocumentResponse
from app.services.audit_service import client_ip, log_action
from app.services.ingestion_service import validate_file, save_file
from app.workers.ingestion_worker import process_document

router = APIRouter(prefix="/documents", tags=["documents"])

# Both viewing and uploading are restricted to manager/admin now —
# field_staff query the knowledge base via /query/answer but don't see
# the raw document library. Kept as one constant so both routes below
# can't quietly drift out of sync with each other.
_DOCUMENT_MANAGER_ROLES = (UserRole.MANAGER, UserRole.ADMIN)


@router.get("", response_model=list[DocumentResponse])
def list_documents(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*_DOCUMENT_MANAGER_ROLES)),
):
    """
    All documents in the (org-wide, shared) knowledge base, most recent
    first. Used by the dashboard to show upload/processing status.
    Restricted to manager/admin — field_staff still query the knowledge
    base via /query/answer, they just don't see the raw document list.
    Includes superseded (old-version) documents too — the UI is
    responsible for showing them as history rather than hiding them
    entirely, since "what did this policy used to say" is itself
    useful audit information.
    """
    return db.query(Document).order_by(desc(Document.created_at)).all()


@router.post("/upload", response_model=DocumentResponse, status_code=202)
def upload_document(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    # Plain multipart form field, not JSON — this endpoint already takes
    # the file as multipart/form-data, so extra fields ride along the
    # same way. Defaults to standard (opt-in restriction, not opt-out).
    restricted: bool = Form(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*_DOCUMENT_MANAGER_ROLES)),
):
    suffix = validate_file(file)

    document_id = uuid.uuid4()
    file_path = save_file(file, document_id, suffix)

    access_level = (
        DocumentAccessLevel.RESTRICTED.value if restricted else DocumentAccessLevel.STANDARD.value
    )

    document = Document(
        id=document_id,
        title=file.filename,
        file_path=file_path,
        doc_type=suffix.lstrip("."),
        status=DocumentStatus.UPLOADING.value,
        access_level=access_level,
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    log_action(
        db,
        action="document.uploaded",
        user=current_user,
        resource_type="document",
        resource_id=document.id,
        detail=document.title,
        ip_address=client_ip(request),
    )

    background_tasks.add_task(process_document, document.id)

    return document


@router.post("/{document_id}/replace", response_model=DocumentResponse, status_code=202)
def replace_document(
    document_id: uuid.UUID,
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    # Restriction level defaults to inheriting the old version's — most
    # of the time a v2 of a restricted safeguarding policy should stay
    # restricted without the uploader having to remember to re-check a
    # box. None here means "not specified"; passing an explicit
    # true/false overrides the inherited value.
    restricted: bool | None = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*_DOCUMENT_MANAGER_ROLES)),
):
    """
    Uploads a new version of an existing document. The OLD document is
    never deleted or overwritten — it's marked is_superseded=True and
    excluded from retrieval going forward (see retrieval_service.py),
    but stays in the document list and audit trail as history. The NEW
    document is a normal Document row, linked back via supersedes_id,
    with version = old.version + 1.
    """
    old_document = db.query(Document).filter(Document.id == document_id).first()
    if old_document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
    if old_document.is_superseded:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This document has already been superseded by a newer version — replace the current version instead.",
        )

    suffix = validate_file(file)
    new_document_id = uuid.uuid4()
    file_path = save_file(file, new_document_id, suffix)

    access_level = (
        old_document.access_level
        if restricted is None
        else (DocumentAccessLevel.RESTRICTED.value if restricted else DocumentAccessLevel.STANDARD.value)
    )

    new_document = Document(
        id=new_document_id,
        title=file.filename,
        file_path=file_path,
        doc_type=suffix.lstrip("."),
        status=DocumentStatus.UPLOADING.value,
        access_level=access_level,
        version=old_document.version + 1,
        supersedes_id=old_document.id,
    )
    db.add(new_document)

    old_document.is_superseded = True

    db.commit()
    db.refresh(new_document)

    log_action(
        db,
        action="document.replaced",
        user=current_user,
        resource_type="document",
        resource_id=new_document.id,
        detail=f"{new_document.title} (v{new_document.version}) replaces {old_document.title} (v{old_document.version})",
        ip_address=client_ip(request),
    )

    background_tasks.add_task(process_document, new_document.id)

    return new_document