from prometheus_client import Counter, Histogram

REQUESTS = Counter("kb_http_requests_total", "HTTP requests", ["method", "route", "status"])
REQUEST_SECONDS = Histogram("kb_http_request_seconds", "HTTP latency", ["route"])
AGENT_SECONDS = Histogram(
    "kb_agent_seconds", "Latency per pipeline stage", ["agent"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 30, 60),
)
ABSTENTIONS = Counter("kb_abstentions_total", "Answers withheld by the confidence gate", ["language"])
QUERIES = Counter("kb_queries_total", "RAG queries", ["language"])
ACL_BLOCKED = Counter("kb_acl_guard_blocked_total", "Chunks removed by the post-retrieval ACL guard (should stay 0)")
INGEST = Counter("kb_ingest_total", "Document ingestion outcomes", ["status"])
INJECTION_FLAGGED = Counter("kb_injection_chunks_flagged_total", "Chunks dropped as suspected prompt injection")
