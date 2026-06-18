"""Minimal filing chunker for RAG. Splits filing text into overlapping word
windows; ids are stable hashes so embeddings can be cached (Q10)."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from app.adapters.protocols import FilingDoc


@dataclass(frozen=True)
class Chunk:
    id: str
    text: str
    form: str


def chunk_text(text: str, size: int = 120, overlap: int = 20) -> list[str]:
    words = text.split()
    if not words:
        return []
    step = max(1, size - overlap)
    return [" ".join(words[i : i + size]) for i in range(0, len(words), step)]


def chunk_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def chunk_filings(filings: list[FilingDoc], size: int = 120, overlap: int = 20) -> list[Chunk]:
    out: list[Chunk] = []
    for f in filings:
        for piece in chunk_text(f.text, size, overlap):
            out.append(Chunk(id=chunk_hash(piece), text=piece, form=f.form))
    return out
