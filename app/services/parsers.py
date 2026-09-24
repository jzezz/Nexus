import csv
import io
from dataclasses import dataclass
from pathlib import Path

from docx import Document as DocxDocument
from pypdf import PdfReader


@dataclass
class ParseResult:
    text: str
    segments: list[dict[str, int | str | None]]
    page_count: int



def extract_text(filename: str, raw_bytes: bytes) -> ParseResult:
    extension = Path(filename).suffix.lower()
    if extension == ".pdf":
        return parse_pdf(raw_bytes)
    if extension == ".docx":
        return parse_docx(raw_bytes)
    if extension == ".csv":
        return parse_csv(raw_bytes)
    raise ValueError("Only PDF, DOCX, and CSV are supported in v1.")



def parse_pdf(raw_bytes: bytes) -> ParseResult:
    reader = PdfReader(io.BytesIO(raw_bytes))
    page_entries: list[dict[str, int | str | None]] = []
    all_text: list[str] = []
    for index, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        if text:
            page_entries.append({"page_number": index, "text": text})
            all_text.append(text)
    if not all_text:
        placeholder = "No extractable PDF text found. OCR should be triggered in a later ingestion pass."
        return ParseResult(text=placeholder, segments=[{"page_number": 1, "text": placeholder}], page_count=max(len(reader.pages), 1))
    return ParseResult(text="\n\n".join(all_text), segments=page_entries, page_count=max(len(reader.pages), len(page_entries), 1))



def parse_docx(raw_bytes: bytes) -> ParseResult:
    document = DocxDocument(io.BytesIO(raw_bytes))
    paragraphs = [paragraph.text.strip() for paragraph in document.paragraphs if paragraph.text.strip()]
    text = "\n".join(paragraphs)
    if not text:
        text = "DOCX parsed successfully, but no paragraph text was found."
    return ParseResult(text=text, segments=[{"page_number": 1, "text": text}], page_count=1)



def parse_csv(raw_bytes: bytes) -> ParseResult:
    decoded = raw_bytes.decode("utf-8", errors="ignore")
    reader = csv.reader(io.StringIO(decoded))
    rows = [" | ".join(cell.strip() for cell in row) for row in reader if any(cell.strip() for cell in row)]
    text = "\n".join(rows)
    if not text:
        text = "CSV parsed successfully, but no non-empty rows were found."
    return ParseResult(text=text, segments=[{"page_number": 1, "text": text}], page_count=1)
