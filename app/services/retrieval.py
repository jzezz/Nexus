import math
import re
from dataclasses import dataclass

from app.models import Chunk, Document

TOKEN_PATTERN = re.compile(r"[a-zA-Z0-9_]+")
SENTENCE_SPLIT_PATTERN = re.compile(r"(?<=[.!?])\s+")
STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "how",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "was",
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
    "with",
}


@dataclass
class RankedChunk:
    document: Document
    chunk: Chunk
    score: float
    matched_terms: list[str]


@dataclass
class RetrievalResult:
    answer: str
    citations: list[dict[str, object]]
    confidence: float



def tokenize(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_PATTERN.findall(text.lower())]



def query_terms(question: str) -> list[str]:
    terms: list[str] = []
    for token in tokenize(question):
        if token in STOPWORDS or len(token) < 3:
            continue
        if token not in terms:
            terms.append(token)
    return terms



def split_sentences(text: str) -> list[str]:
    parts = [part.strip() for part in SENTENCE_SPLIT_PATTERN.split(text) if part.strip()]
    return parts or [text.strip()]



def score_chunk(question: str, terms: list[str], document: Document, chunk: Chunk) -> RankedChunk:
    content = chunk.content.lower()
    filename = document.filename.lower()
    tokens = tokenize(content)
    token_set = set(tokens)
    matched_terms = [term for term in terms if term in token_set]

    if not tokens:
        return RankedChunk(document=document, chunk=chunk, score=0.0, matched_terms=[])

    overlap_score = len(matched_terms) / max(len(terms), 1)
    density_score = sum(tokens.count(term) for term in matched_terms) / max(chunk.token_count or len(tokens), 1)
    phrase_score = 0.0

    compact_question = " ".join(terms[:5])
    if compact_question and compact_question in content:
        phrase_score += 1.0

    filename_score = sum(1 for term in terms if term in filename) * 0.2
    signature_terms = {term.strip() for term in chunk.keyword_signature.lower().split(",") if term.strip()}
    signature_score = sum(1 for term in terms if term in signature_terms) * 0.12
    page_score = 0.05 if chunk.page_number else 0.0
    total_score = overlap_score * 0.55 + density_score * 2.2 + phrase_score + filename_score + signature_score + page_score
    return RankedChunk(document=document, chunk=chunk, score=round(total_score, 4), matched_terms=matched_terms)



def rank_chunks(question: str, documents: list[Document], limit: int = 3) -> list[RankedChunk]:
    terms = query_terms(question)
    ranked: list[RankedChunk] = []
    for document in documents:
        if not document.retrieval_ready:
            continue
        for chunk in document.chunks:
            ranked.append(score_chunk(question, terms, document, chunk))

    ranked.sort(key=lambda item: (item.score, len(item.matched_terms), len(item.chunk.content)), reverse=True)
    return [item for item in ranked[:limit] if item.score > 0]



def build_summary(question: str, ranked_chunks: list[RankedChunk]) -> str:
    if not ranked_chunks:
        return "I could not find enough matching evidence in the indexed documents to answer that confidently."

    summary_lines = ["Answer draft based on the strongest matching chunks:"]
    seen_sentences: set[str] = set()

    for ranked in ranked_chunks:
        added = False
        for sentence in split_sentences(ranked.chunk.content):
            normalized = sentence.strip()
            if len(normalized) < 40 or normalized in seen_sentences:
                continue
            if ranked.matched_terms and not any(term in normalized.lower() for term in ranked.matched_terms):
                continue
            seen_sentences.add(normalized)
            summary_lines.append(f"- {normalized}")
            added = True
            break
        if not added:
            summary_lines.append(f"- {ranked.chunk.content[:220].strip()}")

    summary_lines.append("")
    summary_lines.append(f"Question: {question}")
    return "\n".join(summary_lines)



def confidence_from_scores(ranked_chunks: list[RankedChunk]) -> float:
    if not ranked_chunks:
        return 0.0
    average = sum(item.score for item in ranked_chunks) / len(ranked_chunks)
    return round(min(0.95, math.tanh(average / 2.5)), 2)



def retrieve_answer(question: str, documents: list[Document]) -> RetrievalResult:
    ranked_chunks = rank_chunks(question, documents)
    citations = [
        {
            "document_id": ranked.document.id,
            "filename": ranked.document.filename,
            "snippet": ranked.chunk.content[:220].strip(),
            "page_number": ranked.chunk.page_number,
            "chunk_index": ranked.chunk.chunk_index,
            "score": ranked.score,
        }
        for ranked in ranked_chunks
    ]
    answer = build_summary(question, ranked_chunks)
    confidence = confidence_from_scores(ranked_chunks)
    return RetrievalResult(answer=answer, citations=citations, confidence=confidence)
