"""
Conflict detection API route. Given an existing document, finds
internal policy content elsewhere in the corpus that may give staff
contradictory guidance. Restricted to manager/admin — same tier as
document management and gap detection, since this is a compliance/
program-management tool, not something field staff need.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.v1.auth import require_role
from app.database import get_db
from app.models.user import User, UserRole
from app.schemas.conflict_detection import ConflictAnalysisResponse
from app.services.audit_service import client_ip, log_action
from app.services.conflict_detection_service import analyze_document_conflicts

router = APIRouter(prefix="/conflict-detection", tags=["conflict-detection"])

_CONFLICT_DETECTION_ROLES = (UserRole.MANAGER, UserRole.ADMIN)


@router.post("/analyze/{document_id}", response_model=ConflictAnalysisResponse)
def analyze_conflicts(
    document_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*_CONFLICT_DETECTION_ROLES)),
):
    try:
        result = analyze_document_conflicts(db, document_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    log_action(
        db,
        action="conflict_detection.analyzed",
        user=current_user,
        resource_type="document",
        resource_id=document_id,
        detail=(
            f"document: {result.document_title} | comparisons: {result.comparisons_made} | "
            f"potential_conflicts: {result.potential_conflicts_count}"
        ),
        ip_address=client_ip(request),
    )

    return ConflictAnalysisResponse(
        document_title=result.document_title,
        items=[
            {
                "target_excerpt": item.target_excerpt,
                "target_page": item.target_page,
                "other_document_title": item.other_document_title,
                "other_excerpt": item.other_excerpt,
                "other_page": item.other_page,
                "confidence": item.confidence,
                "explanation": item.explanation,
            }
            for item in result.items
        ],
        chunks_checked=result.chunks_checked,
        comparisons_made=result.comparisons_made,
        potential_conflicts_count=result.potential_conflicts_count,
        truncated=result.truncated,
        summary=result.summary,
    )