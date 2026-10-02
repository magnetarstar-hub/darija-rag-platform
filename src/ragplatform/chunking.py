import re
from dataclasses import dataclass

# split after . ! ? Arabic question mark, Arabic full stop variants, or newline
_SPLIT = re.compile(r"(?<=[.!?؟۔\n])\s+")


@dataclass
class Chunk:
    text: str
    source: str
    page: int = 0


def split_sentences(text: str) -> list[str]:
    return [x.strip() for x in _SPLIT.split(text) if x.strip()]


def _hard_split(s: str, size: int) -> list[str]:
    return [s[i : i + size] for i in range(0, len(s), size)]


def chunk_text(text: str, size: int = 800, overlap: int = 120) -> list[str]:
    """Sentence-aware chunking with character overlap. Works for Arabic and Latin scripts."""
    sentences: list[str] = []
    for s in (x.strip() for x in _SPLIT.split(text)):
        if not s:
            continue
        sentences.extend(_hard_split(s, size) if len(s) > size else [s])

    chunks: list[str] = []
    cur = ""
    for s in sentences:
        if cur and len(cur) + len(s) + 1 > size:
            chunks.append(cur)
            cur = f"{cur[-overlap:]} {s}" if overlap else s
        else:
            cur = f"{cur} {s}".strip()
    if cur:
        chunks.append(cur)
    return chunks
