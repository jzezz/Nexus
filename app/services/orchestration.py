import json

from sqlalchemy.orm import Session

from app import store
from app.models import User
from app.services.retrieval import query_terms, retrieve_answer


DIRECT_TOKENS = {
    "hello",
    "hi",
    "hey",
    "who are you",
    "what can you do",
    "help",
    "thanks",
    "thank you",
}



def route_question(question: str, has_documents: bool, document_scope_requested: bool = False) -> str:
    normalized_question = question.strip().lower().rstrip("!?. ")
    if normalized_question in DIRECT_TOKENS:
        return "direct"
    if document_scope_requested and has_documents:
        return "retrieval"
    if has_documents and query_terms(question):
        return "retrieval"
    return "direct"



def run_chat(
    db: Session,
    user: User,
    question: str,
    conversation_id: str | None,
    document_ids: list[str] | None = None,
) -> tuple[str, str, str, float, list[dict[str, object]], list[str]]:
    requested_document_ids = list(dict.fromkeys(document_ids or []))
    documents = (
        store.list_documents_by_ids(db, user.id, requested_document_ids)
        if requested_document_ids
        else store.list_documents(db, user.id)
    )
    if requested_document_ids and len(documents) != len(requested_document_ids):
        raise ValueError("One or more selected documents are unavailable for this user.")

    conversation = store.get_or_create_conversation(db, conversation_id, user.id)
    route = route_question(question, bool(documents), bool(requested_document_ids))
    scoped_document_ids = [document.id for document in documents]
    store.set_conversation_scope(db, conversation, scoped_document_ids)

    store.append_message(db, conversation.id, "user", question, [])

    if route == "retrieval":
        result = retrieve_answer(question, documents)
        answer = result.answer
        citations = result.citations
        confidence = result.confidence
    else:
        answer = (
            "Nexus AI can search your uploaded documents and return the supporting citations. "
            "Upload a PDF, DOCX, or CSV, then ask a document-specific question to get started."
        )
        citations = []
        confidence = 0.25

    store.append_message(db, conversation.id, "assistant", answer, citations)
    return conversation.id, route, answer, confidence, citations, scoped_document_ids



def parse_message_citations(citations_json: str) -> list[dict[str, object]]:
    try:
        return json.loads(citations_json)
    except json.JSONDecodeError:
        return []
