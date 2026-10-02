"""RAG orchestration. retrieve() and respond() are split so the API can run an authorization guard in between."""
import time
from contextlib import contextmanager

from .acl import AccessScope
from .agents import ABSTAIN, answer_agent, verifier_agent
from .config import Settings
from .embedding import Embedder, Reranker
from .llm import LLM
from .metrics import ABSTENTIONS, AGENT_SECONDS, QUERIES
from .router import detect_language
from .telemetry import span
from .vectorstore import Hit, QdrantStore


@contextmanager
def stage(name: str):
    t0 = time.perf_counter()
    with span(f"agent.{name}"):
        try:
            yield
        finally:
            AGENT_SECONDS.labels(name).observe(time.perf_counter() - t0)


class RAGService:
    def __init__(self, embedder: Embedder, store: QdrantStore, reranker: Reranker, llm: LLM, settings: Settings) -> None:
        self.embedder, self.store, self.reranker, self.llm, self.s = embedder, store, reranker, llm, settings

    def retrieve(self, question: str, scope: AccessScope, document_ids: list[str] | None = None) -> list[Hit]:
        with stage("retrieve"):
            vec = self.embedder.embed([question])[0]
            hits = self.store.search(vec, scope, self.s.candidates_k, document_ids)
            return self.reranker.rerank(question, hits)[: self.s.final_k]

    def respond(self, question: str, hits: list[Hit]) -> dict:
        lang = detect_language(question)
        QUERIES.labels(lang).inc()
        if not hits:
            ABSTENTIONS.labels(lang).inc()
            return {"answer": ABSTAIN[lang], "language": lang, "confidence": 0.0, "abstained": True,
                    "unsupported_claims": [], "sources": []}

        with stage("answer"):
            answer = answer_agent(self.llm, question, hits, lang)
        with stage("verify"):
            verdict = verifier_agent(self.llm, question, answer, hits)

        retrieval_conf = max(0.0, min(1.0, hits[0].score))
        confidence = round(0.6 * verdict["score"] + 0.4 * retrieval_conf, 3)
        abstained = confidence < self.s.abstain_threshold or verdict["score"] < self.s.min_verifier_score
        if abstained:
            ABSTENTIONS.labels(lang).inc()
        return {
            "answer": ABSTAIN[lang] if abstained else answer,
            "language": lang,
            "confidence": confidence,
            "abstained": abstained,
            "unsupported_claims": verdict["unsupported_claims"],
            "sources": [
                {"id": i + 1, "document_id": h.doc_id, "source": h.source, "page": h.page, "score": round(h.score, 3)}
                for i, h in enumerate(hits)
            ],
        }
