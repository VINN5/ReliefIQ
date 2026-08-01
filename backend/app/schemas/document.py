"""
Pydantic schemas for the documents API. Kept separate from the SQLAlchemy
model (app/models/document.py) so the API's public shape can evolve
independently of the database schema.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel


class DocumentResponse(BaseModel):
    id: uuid.UUID
    title: str
    doc_type: str | None
    status: str
    access_level: str
    version: int
    supersedes_id: uuid.UUID | None
    is_superseded: bool
    created_at: datetime

    model_config = {"from_attributes": True}