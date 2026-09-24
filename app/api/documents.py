from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app import store
from app.db import get_db
from app.deps import get_current_user
from app.models import Document, User
from app.schemas import ChunkPreview, DeleteResponse, DocumentInsights, DocumentResponse, UploadResponse
from app.services.document_insights import build_document_insights
from app.services.ingestion import ingest_document

router = APIRouter(tags=["documents"])



def serialize_document(
    document: Document,
    chunk_limit: int | None = 2,
    include_insights: bool = False,
) -> DocumentResponse:
    chunks = document.chunks if chunk_limit is None else document.chunks[:chunk_limit]
    insights = DocumentInsights(**build_document_insights(document)) if include_insights else None
    return DocumentResponse(
        id=document.id,
        filename=document.filename,
        file_type=document.file_type,
        status=document.status,
        page_count=document.page_count,
        chunk_count=document.chunk_count,
        retrieval_ready=document.retrieval_ready,
        processing_error=document.processing_error,
        uploaded_at=document.uploaded_at,
        chunks=[
            ChunkPreview(
                id=chunk.id,
                chunk_index=chunk.chunk_index,
                page_number=chunk.page_number,
                token_count=chunk.token_count,
                keyword_signature=chunk.keyword_signature,
                preview=chunk.content[:120],
            )
            for chunk in chunks
        ],
        insights=insights,
    )


@router.post("/upload", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UploadResponse:
    try:
        document = await ingest_document(db=db, user_id=current_user.id, upload=file)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return UploadResponse(document_id=document.id, filename=document.filename, status=document.status)


@router.get("/documents", response_model=list[DocumentResponse])
def list_documents(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[DocumentResponse]:
    documents = store.list_documents(db, current_user.id)
    return [serialize_document(document, chunk_limit=2) for document in documents]


@router.get("/documents/{document_id}", response_model=DocumentResponse)
def get_document(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DocumentResponse:
    document = store.get_user_document(db, document_id, current_user.id)
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
    return serialize_document(document, chunk_limit=None, include_insights=True)


@router.delete("/documents/{document_id}", response_model=DeleteResponse)
def delete_document(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DeleteResponse:
    deleted = store.delete_user_document(db, document_id, current_user.id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
    return DeleteResponse(success=True)
