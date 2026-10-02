"""Retrieval benchmark with a CI gate.

    python eval/run_eval.py --min-recall 0.8

Indexes eval/corpus/* into an in-memory store (no database, no network when RAG_EMBEDDER=hash),
runs eval/benchmark.jsonl, prints Recall@k / MRR / latency per language and exits 1 if overall
Recall@k < --min-recall.

NOTE: with RAG_EMBEDDER=hash this is a *lexical smoke test* of the plumbing (chunking, ACL filter,
ranking). Real quality gates run with the real embedder + reranker on YOUR corpus (RAG_EMBEDDER=bge).
"""
import argparse
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

from qdrant_client import QdrantClient

from ragplatform.acl import AccessScope
from ragplatform.chunking import chunk_text
from ragplatform.config import Settings
from ragplatform.embedding import build_embedder, build_reranker
from ragplatform.ingestion import read_pages
from ragplatform.router import detect_language
from ragplatform.vectorstore import QdrantStore

TENANT = "eval"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--benchmark", default="eval/benchmark.jsonl")
    ap.add_argument("--corpus", default="eval/corpus")
    ap.add_argument("--min-recall", type=float, default=0.0)
    args = ap.parse_args()

    s = Settings()
    embedder, reranker = build_embedder(s), build_reranker(s)
    store = QdrantStore(QdrantClient(":memory:"), "eval", embedder.dim)
    for f in sorted(Path(args.corpus).iterdir()):
        for page, text in read_pages(f):
            items = [(c, page) for c in chunk_text(text, s.chunk_size, s.chunk_overlap)]
            store.upsert_chunks(
                tenant_id=TENANT, doc_id=f.stem, owner_id="eval", visibility="tenant", group_ids=[],
                source=f.name, items=items, vectors=embedder.embed([t for t, _ in items]),
            )

    scope = AccessScope(TENANT, "eval", frozenset(), True)
    stats = defaultdict(lambda: {"n": 0, "hits": 0, "rr": 0.0, "lat": 0.0})
    for line in Path(args.benchmark).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        t0 = time.perf_counter()
        hits = reranker.rerank(item["question"], store.search(embedder.embed([item["question"]])[0], scope, s.candidates_k))[: s.final_k]
        lat = time.perf_counter() - t0
        kws = [k.lower() for k in item.get("expected_keywords", [])]
        rank = next(
            (i + 1 for i, h in enumerate(hits) if h.source == item["expected_source"] and (not kws or any(k in h.text.lower() for k in kws))),
            None,
        )
        for key in (detect_language(item["question"]), "ALL"):
            st = stats[key]
            st["n"] += 1
            st["hits"] += rank is not None
            st["rr"] += 1 / rank if rank else 0.0
            st["lat"] += lat

    print(f"{'lang':8} {'n':>3} {'recall@' + str(s.final_k):>9} {'MRR':>6} {'lat(ms)':>8}")
    for lang, st in sorted(stats.items()):
        print(f"{lang:8} {st['n']:>3} {st['hits'] / st['n']:>9.2f} {st['rr'] / st['n']:>6.2f} {st['lat'] / st['n'] * 1000:>8.1f}")

    recall = stats["ALL"]["hits"] / stats["ALL"]["n"]
    if recall < args.min_recall:
        print(f"\nFAIL: recall {recall:.2f} < required {args.min_recall:.2f}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
