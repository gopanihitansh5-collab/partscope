"""Deterministic document chunking used for ingestion."""

from __future__ import annotations

import re

SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def split_sentences(text: str) -> list[str]:
    return [s.strip() for s in SENTENCE_SPLIT.split(text) if s.strip()]


def chunk_text(text: str, max_words: int = 110, overlap_words: int = 20) -> list[str]:
    sentences = split_sentences(text)
    chunks: list[str] = []
    current: list[str] = []
    current_words = 0

    for sentence in sentences:
        words = sentence.split()
        if current and current_words + len(words) > max_words:
            chunks.append(" ".join(current))
            tail = " ".join(current).split()[-overlap_words:]
            current = [" ".join(tail)] if tail else []
            current_words = len(tail)
        current.append(sentence)
        current_words += len(words)

    if current:
        chunks.append(" ".join(current))
    return [c for c in chunks if c.strip()]
