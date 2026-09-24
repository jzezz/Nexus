import json

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Chunk, Conversation, Document, Message, User



def get_user_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email))



def create_user(db: Session, email: str, password_hash: str) -> User:
    user = User(email=email, password_hash=password_hash)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user



def create_document(
    db: Session,
    user_id: str,
    filename: str,
    file_type: str,
    text: str,
    status: str = "processing",
) -> Document:
    document = Document(
        user_id=user_id,
        filename=filename,
        file_type=file_type,
        status=status,
        extracted_text=text,
        page_count=0,
        chunk_count=0,
        retrieval_ready=False,
        processing_error=None,
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document



def attach_chunks(
    db: Session,
    document: Document,
    chunks: list[dict[str, object]],
    extracted_text: str,
    page_count: int,
) -> Document:
    for chunk in chunks:
        db.add(
            Chunk(
                document_id=document.id,
                content=str(chunk["content"]),
                chunk_index=int(chunk["chunk_index"]),
                page_number=chunk["page_number"],
                token_count=int(chunk.get("token_count", 0)),
                keyword_signature=str(chunk.get("keyword_signature", "")),
                embedding_id=chunk.get("embedding_id"),
            )
        )

    document.extracted_text = extracted_text
    document.page_count = page_count
    document.chunk_count = len(chunks)
    document.retrieval_ready = len(chunks) > 0
    document.processing_error = None
    document.status = "processed"
    db.commit()
    return get_document(db, document.id)



def mark_document_failed(db: Session, document_id: str, error_message: str) -> None:
    document = db.get(Document, document_id)
    if not document:
        return
    document.status = "failed"
    document.processing_error = error_message[:1000]
    document.retrieval_ready = False
    db.commit()



def list_documents(db: Session, user_id: str) -> list[Document]:
    return list(
        db.scalars(
            select(Document)
            .where(Document.user_id == user_id)
            .options(selectinload(Document.chunks))
            .order_by(Document.uploaded_at.desc())
        )
    )



def list_documents_by_ids(db: Session, user_id: str, document_ids: list[str]) -> list[Document]:
    if not document_ids:
        return []
    return list(
        db.scalars(
            select(Document)
            .where(Document.user_id == user_id, Document.id.in_(document_ids))
            .options(selectinload(Document.chunks))
            .order_by(Document.uploaded_at.desc())
        )
    )



def get_document(db: Session, document_id: str) -> Document:
    document = db.scalar(select(Document).where(Document.id == document_id).options(selectinload(Document.chunks)))
    if not document:
        raise ValueError("Document not found.")
    return document



def get_user_document(db: Session, document_id: str, user_id: str) -> Document | None:
    return db.scalar(
        select(Document)
        .where(Document.id == document_id, Document.user_id == user_id)
        .options(selectinload(Document.chunks))
    )



def delete_user_document(db: Session, document_id: str, user_id: str) -> bool:
    document = db.scalar(select(Document).where(Document.id == document_id, Document.user_id == user_id))
    if not document:
        return False
    db.delete(document)
    db.commit()
    return True



def parse_scoped_document_ids(raw_value: str | None) -> list[str]:
    if not raw_value:
        return []
    try:
        parsed = json.loads(raw_value)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return [item for item in parsed if isinstance(item, str)]



def get_or_create_conversation(db: Session, conversation_id: str | None, user_id: str) -> Conversation:
    if conversation_id:
        conversation = db.get(Conversation, conversation_id)
        if conversation and conversation.user_id == user_id:
            return conversation
    conversation = Conversation(user_id=user_id, scoped_document_ids_json="[]")
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation



def set_conversation_scope(db: Session, conversation: Conversation, document_ids: list[str]) -> Conversation:
    conversation.scoped_document_ids_json = json.dumps(list(dict.fromkeys(document_ids)))
    db.commit()
    db.refresh(conversation)
    return conversation



def list_conversations(db: Session, user_id: str) -> list[Conversation]:
    return list(
        db.scalars(
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .options(selectinload(Conversation.messages))
            .order_by(Conversation.created_at.desc())
        )
    )



def get_conversation(db: Session, conversation_id: str, user_id: str) -> Conversation | None:
    conversation = db.scalar(
        select(Conversation)
        .where(Conversation.id == conversation_id, Conversation.user_id == user_id)
        .options(selectinload(Conversation.messages))
    )
    if not conversation:
        return None
    return conversation



def delete_conversation(db: Session, conversation_id: str, user_id: str) -> bool:
    conversation = db.scalar(select(Conversation).where(Conversation.id == conversation_id, Conversation.user_id == user_id))
    if not conversation:
        return False
    db.delete(conversation)
    db.commit()
    return True



def append_message(db: Session, conversation_id: str, role: str, content: str, citations: list[dict[str, object]]) -> Message:
    message = Message(
        conversation_id=conversation_id,
        role=role,
        content=content,
        citations_json=json.dumps(citations),
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return message



def get_history(db: Session, conversation_id: str) -> list[Message]:
    return list(
        db.scalars(
            select(Message).where(Message.conversation_id == conversation_id).order_by(Message.created_at.asc())
        )
    )
