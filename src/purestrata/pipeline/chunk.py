"""Split long text blocks into overlapping chunks sized for retrieval."""

from __future__ import annotations

import re

_SENTENCE_END_RE = re.compile(r"(?<=[。．!?!?;；.])\s*")


def _split_sentences(text: str) -> list[str]:
    parts = _SENTENCE_END_RE.split(text)
    return [p for p in (s.strip() for s in parts) if p]


def _slice_by_sentences(paragraph: str, target: int) -> list[str]:
    pieces: list[str] = []
    current = ""
    for sentence in _split_sentences(paragraph):
        candidate = f"{current} {sentence}".strip() if current else sentence
        if len(candidate) <= target or not current:
            current = candidate
        else:
            pieces.append(current)
            current = sentence
        while len(current) > target:
            pieces.append(current[:target])
            current = current[target:]
    if current:
        pieces.append(current)
    return pieces


def split_long_text(text: str, target: int = 800, overlap: int = 120) -> list[str]:
    """Split ``text`` into chunks of about ``target`` characters.

    Paragraph boundaries are preferred, then sentence boundaries, then raw
    characters. Consecutive chunks overlap by ``overlap`` characters so
    sentences cut at a boundary stay retrievable from both sides.
    """
    if not text.strip():
        return []
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        candidate = f"{current}\n\n{paragraph}" if current else paragraph
        if len(candidate) <= target:
            current = candidate
            continue
        if current:
            chunks.append(current)
        if len(paragraph) <= target:
            current = paragraph
        else:
            chunks.extend(_slice_by_sentences(paragraph, target))
    if current:
        chunks.append(current)
    if overlap > 0 and len(chunks) > 1:
        overlapped = [chunks[0]]
        for prev, chunk in zip(chunks, chunks[1:], strict=False):
            if len(prev) <= target:
                overlapped.append(prev[-overlap:] + "\n" + chunk)
            else:
                overlapped.append(chunk)
        chunks = overlapped
    return chunks
