"""
Conversations API — powers the chat sidebar (list past conversations,
most recently active first) and thread view (fetch one conversation's
full message history). Creating a new conversation and adding messages
both happen through POST /query/answer, not here — see query.py.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.v1.auth import get_current_user
from app.database import get_db
from app.models.conversation import Conversation
from app.models.query_history import QueryHistory
from app.models.user import User
from app.schemas.conversation import ConversationMessage, ConversationSummary

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get("", response_model=list[ConversationSummary])
def list_conversations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Sidebar data: the current user's own conversations, most recently
    active first (updated_at, not created_at — sending a new message
    in an old conversation should bump it back to the top).
    """
    return (
        db.query(Conversation)
        .filter(Conversation.user_id == current_user.id)
        .order_by(Conversation.updated_at.desc())
        .all()
    )


@router.get("/{conversation_id}/messages", response_model=list[ConversationMessage])
def get_conversation_messages(
    conversation_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Full thread for one conversation, oldest first (chat reading order).
    404s rather than 403s if the conversation belongs to someone else —
    this avoids confirming to a caller that a given conversation ID
    exists at all if it isn't theirs.
    """
    conversation = (
        db.query(Conversation)
        .filter(Conversation.id == conversation_id, Conversation.user_id == current_user.id)
        .first()
    )
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.")

    return (
        db.query(QueryHistory)
        .filter(QueryHistory.conversation_id == conversation_id)
        .order_by(QueryHistory.created_at.asc())
        .all()
    )


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(
    conversation_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Deletes a conversation the caller owns. All of its QueryHistory
    turns are removed automatically at the database level — see
    QueryHistory.conversation_id's ondelete="CASCADE" — so there's no
    separate cleanup step needed here. Any user can delete their own
    conversations; this isn't role-gated, since it's personal data,
    not something requiring manager/admin oversight.
    """
    conversation = (
        db.query(Conversation)
        .filter(Conversation.id == conversation_id, Conversation.user_id == current_user.id)
        .first()
    )
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.")

    db.delete(conversation)
    db.commit()