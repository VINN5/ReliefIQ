"""
Pydantic schemas for the spreadsheet preview and comparison API.
"""

import uuid

from pydantic import BaseModel


class SpreadsheetTableResponse(BaseModel):
    id: uuid.UUID
    sheet_name: str
    headers: list[str]
    rows: list[list]
    row_count: int

    model_config = {"from_attributes": True}


class SheetComparisonResponse(BaseModel):
    sheet_name: str
    columns_added: list[str]
    columns_removed: list[str]
    rows_added: list[list]
    rows_removed: list[list]
    old_row_count: int
    new_row_count: int
    headers: list[str]
    truncated: bool


class SpreadsheetComparisonResponse(BaseModel):
    old_document_title: str
    new_document_title: str
    sheets_added: list[str]
    sheets_removed: list[str]
    sheet_comparisons: list[SheetComparisonResponse]
    summary: str