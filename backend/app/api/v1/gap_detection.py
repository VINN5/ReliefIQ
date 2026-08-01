"""
Gap detection API route. Accepts EITHER an uploaded PDF or pasted text
containing a donor's policy requirements, and compares each requirement
against the organisation's own internal policies (via the same
retrieval pipeline used everywhere else) to flag coverage gaps.

Restricted to manager/admin — same tier as document management, since
this is a compliance/program-management tool, not something field
staff need.

The donor document itself is NOT stored, chunked, or embedded. It's a
one-off analysis input — see gap_detection_service module docstring.
"""

from fastapi import APIRouter, Depends, Form, HTTPException, Request, UploadFile, File, status
from sqlalchemy.orm import Session

from app.api.v1.auth import require_role
from app.database import get_db
from app.models.user import User, UserRole
from app.schemas.gap_detection import GapAnalysisResponse
from app.services.audit_service import client_ip, log_action
from app.services.gap_detection_service import analyze_gaps, extract_text_from_pdf

router = APIRouter(prefix="/gap-detection", tags=["gap-detection"])

_GAP_DETECTION_ROLES = (UserRole.MANAGER, UserRole.ADMIN)


@router.post("/analyze", response_model=GapAnalysisResponse)
def analyze_donor_policy(
    request: Request,
    file: UploadFile | None = File(None),
    text: str | None = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*_GAP_DETECTION_ROLES)),
):
    if not file and not (text and text.strip()):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide either a PDF file or pasted text to analyze.",
        )
    if file and text and text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide only one of: a PDF file, or pasted text — not both.",
        )

    if file:
        if not file.filename.lower().endswith(".pdf"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only PDF files are supported for gap detection uploads.",
            )
        file_bytes = file.file.read()
        donor_text = extract_text_from_pdf(file_bytes)
        source_label = file.filename
    else:
        donor_text = text.strip()
        source_label = "pasted text"

    if not donor_text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No readable text was found in the provided document.",
        )

    result = analyze_gaps(db, donor_text, requester_role=current_user.role)

    log_action(
        db,
        action="gap_detection.analyzed",
        user=current_user,
        detail=(
            f"source: {source_label} | requirements: {result.total_requirements} | "
            f"covered: {result.covered_count} | partial: {result.partial_count} | "
            f"gap: {result.gap_count}"
        ),
        ip_address=client_ip(request),
    )

    return GapAnalysisResponse(
        items=[
            {
                "requirement": item.requirement,
                "status": item.status,
                "explanation": item.explanation,
                "matched_documents": item.matched_documents,
            }
            for item in result.items
        ],
        covered_count=result.covered_count,
        partial_count=result.partial_count,
        gap_count=result.gap_count,
        total_requirements=result.total_requirements,
        summary=result.summary,
        truncated=result.truncated,
    )