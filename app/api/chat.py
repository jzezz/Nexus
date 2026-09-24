from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import store
from app.db import get_db
from app.deps import get_current_user
from app.models import Conversation, User
from app.schemas import ChatRequest, ChatResponse, Citation, ConversationSummary, DeleteResponse, HistoryMessage
from app.services.orchestration import parse_message_citations, run_chat

router = APIRouter(tags=["chat"])



def build_conversation_summary(conversation: Conversation) -> ConversationSummary:
    messages = sorted(conversation.messages, key=lambda message: message.created_at)
    first_user_message = next((message for message in messages if message.role == "user"), None)
    last_message = messages[-1] if messages else None

    title_source = first_user_message.content if first_user_message else "New conversation"
    title = title_source.strip().replace("\n", " ")[:80] or "New conversation"
    last_preview = last_message.content.strip().replace("\n", " ")[:120] if last_message else "No messages yet."
    updated_at = last_message.created_at if last_message else conversation.created_at

    return ConversationSummary(
        id=conversation.id,
        title=title,
        message_count=len(messages),
        created_at=conversation.created_at,
        updated_at=updated_at,
        last_message_preview=last_preview,
        scoped_document_ids=store.parse_scoped_document_ids(conversation.scoped_document_ids_json),
    )


@router.get("/conversations", response_model=list[ConversationSummary])
def conversations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ConversationSummary]:
    return [build_conversation_summary(conversation) for conversation in store.list_conversations(db, current_user.id)]


@router.delete("/conversations/{conversation_id}", response_model=DeleteResponse)
def delete_conversation(
    conversation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DeleteResponse:
    deleted = store.delete_conversation(db, conversation_id, current_user.id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.")
    return DeleteResponse(success=True)


@router.post("/chat", response_model=ChatResponse)
def chat(
    payload: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ChatResponse:
    try:
        conversation_id, route, answer, confidence, citations, scoped_document_ids = run_chat(
            db=db,
            user=current_user,
            question=payload.question,
            conversation_id=payload.conversation_id,
            document_ids=payload.document_ids,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return ChatResponse(
        conversation_id=conversation_id,
        route=route,
        answer=answer,
        confidence=confidence,
        citations=[Citation(**citation) for citation in citations],
        scoped_document_ids=scoped_document_ids,
    )


@router.get("/history", response_model=list[HistoryMessage])
def history(
    conversation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[HistoryMessage]:
    conversation = store.get_conversation(db, conversation_id, current_user.id)
    if not conversation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.")
    return [
        HistoryMessage(
            id=message.id,
            conversation_id=message.conversation_id,
            role=message.role,
            content=message.content,
            citations=[Citation(**citation) for citation in parse_message_citations(message.citations_json)],
            created_at=message.created_at,
        )
        for message in store.get_history(db, conversation.id)
    ]
