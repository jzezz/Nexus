from collections import Counter

from app.models import Document
from app.services.retrieval import STOPWORDS, split_sentences, tokenize

MAX_TOPICS = 6
MAX_SUGGESTED_QUESTIONS = 5
MIN_SENTENCE_LENGTH = 45



def _extract_topic_candidates(document: Document) -> list[str]:
    candidates: list[str] = []

    for chunk in document.chunks:
        signature_terms = [term.strip().lower() for term in chunk.keyword_signature.split(",") if term.strip()]
        candidates.extend(signature_terms)

    if not candidates:
        candidates.extend(tokenize(document.extracted_text))

    normalized: list[str] = []
    for term in candidates:
        if term in STOPWORDS or len(term) < 4 or term.isdigit():
            continue
        normalized.append(term)
    return normalized



def extract_key_topics(document: Document, limit: int = MAX_TOPICS) -> list[str]:
    counts = Counter(_extract_topic_candidates(document))
    return [term.replace("_", " ") for term, _count in counts.most_common(limit)]



def summarize_document(document: Document) -> str:
    source_text = document.extracted_text.strip() if document.extracted_text else ""
    topics = set(extract_key_topics(document, limit=4))

    sentences: list[str] = []
    if source_text:
        sentences = split_sentences(source_text)
    if not sentences:
        for chunk in document.chunks:
            sentences.extend(split_sentences(chunk.content))

    ranked_sentences: list[tuple[float, str]] = []
    seen: set[str] = set()
    for sentence in sentences:
        normalized = sentence.strip()
        lowered = normalized.lower()
        if len(normalized) < MIN_SENTENCE_LENGTH or lowered in seen:
            continue
        seen.add(lowered)
        topic_hits = sum(1 for topic in topics if topic in lowered)
        token_count = len(tokenize(normalized))
        score = topic_hits * 2 + min(token_count / 18, 3)
        ranked_sentences.append((score, normalized))

    ranked_sentences.sort(key=lambda item: (item[0], len(item[1])), reverse=True)
    chosen = [sentence for _score, sentence in ranked_sentences[:3]]

    if chosen:
        return " ".join(chosen)

    if document.chunks:
        return document.chunks[0].content[:320].strip()

    if source_text:
        return source_text[:320].strip()

    return "No document summary is available yet."



def build_suggested_questions(document: Document, topics: list[str]) -> list[str]:
    filename = document.filename
    suggestions = [
        f"What are the main takeaways from {filename}?",
        f"Summarize the most important points in {filename}.",
    ]

    for topic in topics[:3]:
        suggestions.append(f"What does this document say about {topic}?")
        suggestions.append(f"Which details in {filename} are most relevant to {topic}?")

    unique: list[str] = []
    seen: set[str] = set()
    for item in suggestions:
        lowered = item.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        unique.append(item)
        if len(unique) >= MAX_SUGGESTED_QUESTIONS:
            break
    return unique



def build_document_insights(document: Document) -> dict[str, object]:
    topics = extract_key_topics(document)
    return {
        "summary": summarize_document(document),
        "key_topics": topics,
        "suggested_questions": build_suggested_questions(document, topics),
    }
