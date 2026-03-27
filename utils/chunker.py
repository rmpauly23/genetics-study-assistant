"""Text extraction from PDFs and Google Docs, plus chunking logic."""

import io
import re
from dataclasses import dataclass, field
from typing import Optional

try:
    import pdfplumber
    PDF_BACKEND = "pdfplumber"
except ImportError:
    try:
        from pypdf import PdfReader
        PDF_BACKEND = "pypdf"
    except ImportError:
        PDF_BACKEND = None


# Approximate characters per token (rough estimate for English text)
CHARS_PER_TOKEN = 4


@dataclass
class Chunk:
    """A text chunk with metadata for retrieval."""
    text: str
    source_name: str
    chunk_index: int
    page_number: Optional[int] = None
    token_estimate: int = 0

    def __post_init__(self):
        if self.token_estimate == 0:
            self.token_estimate = max(1, len(self.text) // CHARS_PER_TOKEN)

    @property
    def citation(self) -> str:
        """Human-readable citation string."""
        loc = f" (p. {self.page_number})" if self.page_number else f" (chunk {self.chunk_index + 1})"
        return f"{self.source_name}{loc}"


def extract_text_from_pdf_bytes(pdf_bytes: bytes, source_name: str) -> list[tuple[str, int]]:
    """
    Extract text page-by-page from PDF bytes.
    Returns list of (page_text, page_number) tuples.
    """
    pages = []
    if not pdf_bytes:
        return pages

    if PDF_BACKEND == "pdfplumber":
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for i, page in enumerate(pdf.pages, start=1):
                text = page.extract_text() or ""
                text = _clean_text(text)
                if text.strip():
                    pages.append((text, i))

    elif PDF_BACKEND == "pypdf":
        reader = PdfReader(io.BytesIO(pdf_bytes))
        for i, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            text = _clean_text(text)
            if text.strip():
                pages.append((text, i))

    else:
        raise RuntimeError("No PDF library available. Install pdfplumber or pypdf.")

    return pages


def extract_text_from_gdoc(raw_text: str) -> list[tuple[str, int]]:
    """
    Convert plain-text Google Doc export into paragraph blocks.
    Returns list of (paragraph_text, block_index) tuples.
    """
    paragraphs = [p.strip() for p in raw_text.split("\n\n") if p.strip()]
    return [(p, i + 1) for i, p in enumerate(paragraphs)]


def _clean_text(text: str) -> str:
    """Remove excessive whitespace and non-printable characters."""
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    text = re.sub(r" {3,}", "  ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def chunk_text(
    text_blocks: list[tuple[str, int]],
    source_name: str,
    chunk_token_size: int = 1000,
    overlap_tokens: int = 100,
) -> list[Chunk]:
    """
    Split text blocks into overlapping chunks of ~chunk_token_size tokens.

    Args:
        text_blocks: List of (text, page_or_block_number).
        source_name: Display name for citations.
        chunk_token_size: Target tokens per chunk.
        overlap_tokens: Tokens of overlap between adjacent chunks.

    Returns:
        List of Chunk objects.
    """
    chunk_chars = chunk_token_size * CHARS_PER_TOKEN
    overlap_chars = overlap_tokens * CHARS_PER_TOKEN

    # Flatten all text into a single string, tracking page boundaries
    full_text = ""
    page_boundaries: list[tuple[int, int]] = []  # (char_offset, page_number)

    for text, page_num in text_blocks:
        page_boundaries.append((len(full_text), page_num))
        full_text += text + "\n\n"

    if not full_text.strip():
        return []

    def _page_at_offset(offset: int) -> Optional[int]:
        page = None
        for char_offset, page_num in page_boundaries:
            if char_offset <= offset:
                page = page_num
            else:
                break
        return page

    chunks: list[Chunk] = []
    start = 0
    chunk_index = 0

    while start < len(full_text):
        end = start + chunk_chars

        # Try to break on a sentence boundary (. ! ?) or paragraph
        if end < len(full_text):
            # Prefer paragraph break
            para_break = full_text.rfind("\n\n", start, end)
            if para_break != -1 and para_break > start + overlap_chars:
                end = para_break + 2
            else:
                # Fall back to sentence end
                for punct in (". ", "! ", "? "):
                    sent_break = full_text.rfind(punct, start, end)
                    if sent_break != -1 and sent_break > start + overlap_chars:
                        end = sent_break + len(punct)
                        break

        chunk_text_str = full_text[start:end].strip()
        if chunk_text_str:
            page_num = _page_at_offset(start)
            chunks.append(
                Chunk(
                    text=chunk_text_str,
                    source_name=source_name,
                    chunk_index=chunk_index,
                    page_number=page_num,
                )
            )
            chunk_index += 1

        # Advance with overlap
        start = end - overlap_chars
        if start <= 0 and end >= len(full_text):
            break

    return chunks


def chunks_from_pdf(pdf_bytes: bytes, source_name: str, **kwargs) -> list[Chunk]:
    """Convenience wrapper: PDF bytes -> Chunk list."""
    blocks = extract_text_from_pdf_bytes(pdf_bytes, source_name)
    return chunk_text(blocks, source_name, **kwargs)


def chunks_from_gdoc(raw_text: str, source_name: str, **kwargs) -> list[Chunk]:
    """Convenience wrapper: Google Doc plain text -> Chunk list."""
    blocks = extract_text_from_gdoc(raw_text)
    return chunk_text(blocks, source_name, **kwargs)
