import hashlib
import math
from typing import Protocol

from .config import Settings
from .text import tokenize
from .vectorstore import Hit


class Embedder(Protocol):
    dim: int

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class Reranker(Protocol):
    def rerank(self, query: str, hits: list[Hit]) -> list[Hit]: ...


class HashEmbedder:
    """Deterministic lexical embedder (hashed bag of words). For tests/CI only: no semantics, no downloads."""

    def __init__(self, dim: int = 256) -> None:
        self.dim = dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        out = []
        for t in texts:
            v = [0.0] * self.dim
            for tok in tokenize(t):
                v[int(hashlib.md5(tok.encode()).hexdigest(), 16) % self.dim] += 1.0
            norm = math.sqrt(sum(x * x for x in v)) or 1.0
            out.append([x / norm for x in v])
        return out


class BGEEmbedder:
    def __init__(self, model: str, dim: int) -> None:
        self.model_name, self.dim, self._model = model, dim, None

    def embed(self, texts: list[str]) -> list[list[float]]:
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model_name)
        return self._model.encode(texts, normalize_embeddings=True, batch_size=16).tolist()


class NullReranker:
    def rerank(self, query: str, hits: list[Hit]) -> list[Hit]:
        return sorted(hits, key=lambda h: h.score, reverse=True)


class CrossEncoderReranker:
    def __init__(self, model: str) -> None:
        self.model_name, self._model = model, None

    def rerank(self, query: str, hits: list[Hit]) -> list[Hit]:
        if not hits:
            return hits
        if self._model is None:
            from sentence_transformers import CrossEncoder

            self._model = CrossEncoder(self.model_name)
        scores = self._model.predict([(query, h.text) for h in hits])
        for h, s in zip(hits, scores, strict=True):
            h.score = float(s)
        return sorted(hits, key=lambda h: h.score, reverse=True)


def build_embedder(s: Settings) -> Embedder:
    return HashEmbedder() if s.embedder == "hash" else BGEEmbedder(s.embed_model, s.embed_dim)


def build_reranker(s: Settings) -> Reranker:
    return NullReranker() if s.reranker == "none" else CrossEncoderReranker(s.rerank_model)
