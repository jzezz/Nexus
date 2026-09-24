import re
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from app import store
from app.config import settings
from app.models import Document
from app.services.parsers import ParseResult, extract_text
from app.services.retrieval import query_terms, tokenize

CHUNK_SIZE = 700
OVERLAP = 100
SUPPORTED_TYPES = {".pdf", ".docx", ".csv"}
KEYWORD_LIMIT = 8
FILENAME_SANITIZER = re.compile(r"[^A-Za-z0-9._ -]")


@dataclass
class ChunkPayload:
    content: str
    chunk_index: int
    page_number: int | None
    token_count: int
    keyword_signature: str



def sanitize_filename(filename: str) -> str:
    cleaned = FILENAME_SANITIZER.sub("_", Path(filename).name.strip())
    return cleaned[:180] or "document"



def validate_upload(raw_bytes: bytes) -> None:
    if not raw_bytes:
        raise ValueError("Uploaded file is empty.")
    if len(raw_bytes) > settings.max_upload_size_bytes:
        raise ValueError(f"Uploaded file exceeds the {settings.max_upload_size_mb} MB limit.")


async def ingest_document(db: Session, user_id: str, upload) -> Document:
    safe_filename = sanitize_filename(upload.filename or "document")
    extension = Path(safe_filename).suffix.lower()
    if extension not in SUPPORTED_TYPES:
        raise ValueError("Only PDF, DOCX, and CSV are supported in v1.")

    raw_bytes = await upload.read()
    validate_upload(raw_bytes)

    document = store.create_document(
        db=db,
        user_id=user_id,
        filename=safe_filename,
        file_type=extension.lstrip("."),
        text="",
        status="processing",
    )

    try:
        parse_result = extract_text(safe_filename, raw_bytes)
        chunks = make_chunks(parse_result)
        return store.attach_chunks(
            db,
            document,
            chunks=[chunk.__dict__ for chunk in chunks],
            extracted_text=parse_result.text,
            page_count=parse_result.page_count,
        )
    except Exception as exc:
        store.mark_document_failed(db, document.id, str(exc))
        raise ValueError(f"Could not extract readable text from {safe_filename}.") from exc



def make_chunks(parse_result: ParseResult) -> list[ChunkPayload]:
    chunks: list[ChunkPayload] = []
    chunk_index = 0
    for segment in parse_result.segments:
        text = str(segment["text"]).strip()
        page_number = segment.get("page_number")
        if len(text) <= CHUNK_SIZE:
            chunks.append(build_chunk_payload(text, chunk_index, page_number))
            chunk_index += 1
            continue

        start = 0
        while start < len(text):
            end = min(start + CHUNK_SIZE, len(text))
            chunks.append(build_chunk_payload(text[start:end], chunk_index, page_number))
            chunk_index += 1
            if end == len(text):
                break
            start = max(end - OVERLAP, start + 1)
    return chunks



def build_chunk_payload(text: str, chunk_index: int, page_number: int | None) -> ChunkPayload:
    tokens = tokenize(text)
    keywords = query_terms(text)[:KEYWORD_LIMIT]
    return ChunkPayload(
        content=text,
        chunk_index=chunk_index,
        page_number=page_number,
        token_count=len(tokens),
        keyword_signature=", ".join(keywords),
    )
