from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    email: EmailStr


class UploadResponse(BaseModel):
    document_id: str
    filename: str
    status: str


class ChunkPreview(BaseModel):
    id: str
    chunk_index: int
    page_number: int | None = None
    token_count: int = 0
    keyword_signature: str = ""
    preview: str


class DocumentInsights(BaseModel):
    summary: str
    key_topics: list[str] = Field(default_factory=list)
    suggested_questions: list[str] = Field(default_factory=list)


class DocumentResponse(BaseModel):
    id: str
    filename: str
    file_type: str
    status: str
    page_count: int = 0
    chunk_count: int = 0
    retrieval_ready: bool = False
    processing_error: str | None = None
    uploaded_at: datetime
    chunks: list[ChunkPreview] = Field(default_factory=list)
    insights: DocumentInsights | None = None


class Citation(BaseModel):
    document_id: str
    filename: str
    snippet: str
    page_number: int | None = None
    chunk_index: int | None = None
    score: float | None = None


class ChatRequest(BaseModel):
    conversation_id: str | None = None
    question: str = Field(min_length=3, max_length=4000)
    document_ids: list[str] = Field(default_factory=list)


class ChatResponse(BaseModel):
    conversation_id: str
    answer: str
    route: str
    confidence: float
    citations: list[Citation]
    scoped_document_ids: list[str] = Field(default_factory=list)


class HistoryMessage(BaseModel):
    id: str
    conversation_id: str
    role: str
    content: str
    citations: list[Citation]
    created_at: datetime


class ConversationSummary(BaseModel):
    id: str
    title: str
    message_count: int
    created_at: datetime
    updated_at: datetime
    last_message_preview: str
    scoped_document_ids: list[str] = Field(default_factory=list)


class DeleteResponse(BaseModel):
    success: bool


class HealthResponse(BaseModel):
    status: str
    environment: str


class ReadyResponse(BaseModel):
    status: str
    environment: str
    database: str
