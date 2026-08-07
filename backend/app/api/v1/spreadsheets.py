"""
Spreadsheet analysis API — preview parsed tables and compare a
spreadsheet against the version it replaced. Restricted to
manager/admin, same tier as document management.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.v1.auth import require_role
from app.database import get_db
from app.models.document import Document
from app.models.spreadsheet_table import SpreadsheetTable
from app.models.user import User, UserRole
from app.schemas.spreadsheet import SpreadsheetComparisonResponse, SpreadsheetTableResponse
from app.services.audit_service import client_ip, log_action
from app.services.spreadsheet_comparison_service import compare_spreadsheet_versions

router = APIRouter(prefix="/spreadsheets", tags=["spreadsheets"])

_SPREADSHEET_ROLES = (UserRole.MANAGER, UserRole.ADMIN)


@router.get("/{document_id}/tables", response_model=list[SpreadsheetTableResponse])
def get_spreadsheet_tables(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*_SPREADSHEET_ROLES)),
):
    document = db.query(Document).filter(Document.id == document_id).first()
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
    if document.doc_type not in ("xlsx", "csv"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This document isn't a spreadsheet.")

    return (
        db.query(SpreadsheetTable)
        .filter(SpreadsheetTable.document_id == document_id)
        .order_by(SpreadsheetTable.sheet_name)
        .all()
    )


@router.post("/{document_id}/compare", response_model=SpreadsheetComparisonResponse)
def compare_spreadsheets(
    document_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*_SPREADSHEET_ROLES)),
):
    try:
        result = compare_spreadsheet_versions(db, document_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    log_action(
        db,
        action="spreadsheet.compared",
        user=current_user,
        resource_type="document",
        resource_id=document_id,
        detail=f"'{result.new_document_title}' vs '{result.old_document_title}'",
        ip_address=client_ip(request),
    )

    return SpreadsheetComparisonResponse(
        old_document_title=result.old_document_title,
        new_document_title=result.new_document_title,
        sheets_added=result.sheets_added,
        sheets_removed=result.sheets_removed,
        sheet_comparisons=[
            {
                "sheet_name": c.sheet_name,
                "columns_added": c.columns_added,
                "columns_removed": c.columns_removed,
                "rows_added": c.rows_added,
                "rows_removed": c.rows_removed,
                "old_row_count": c.old_row_count,
                "new_row_count": c.new_row_count,
                "headers": c.headers,
                "truncated": c.truncated,
            }
            for c in result.sheet_comparisons
        ],
        summary=result.summary,
    )