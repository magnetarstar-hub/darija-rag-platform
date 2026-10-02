from dataclasses import dataclass

from qdrant_client import QdrantClient

from .config import Settings
from .embedding import Embedder, Reranker, build_embedder, build_reranker
from .llm import LLM, build_llm
from .rag import RAGService
from .vectorstore import QdrantStore


@dataclass
class Services:
    embedder: Embedder
    store: QdrantStore
    reranker: Reranker
    llm: LLM
    rag: RAGService


def make_services(settings: Settings, embedder: Embedder, store: QdrantStore, reranker: Reranker, llm: LLM) -> Services:
    return Services(embedder, store, reranker, llm, RAGService(embedder, store, reranker, llm, settings))


def build_services(settings: Settings) -> Services:
    client = QdrantClient(url=settings.qdrant_url) if settings.qdrant_url else QdrantClient(path=settings.qdrant_path)
    embedder = build_embedder(settings)
    store = QdrantStore(client, settings.collection, embedder.dim)
    return make_services(settings, embedder, store, build_reranker(settings), build_llm(settings))
