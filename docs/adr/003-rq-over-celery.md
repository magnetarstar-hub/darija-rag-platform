# ADR-003: RQ for ingestion jobs

**Status:** accepted

**Context.** Ingestion (parse, embed) is slow and must not block requests. Celery is more featureful; RQ is far smaller.

**Decision.** Use RQ on Redis with `Retry(max=3, interval=[10, 30, 60])`. Jobs are idempotent and report state on the `Document`
row (`queued -> processing -> ready | failed`). `RAG_QUEUE_MODE=inline` runs jobs synchronously for dev and tests.

**Consequences.** Simple operations and easy local debugging; no built-in scheduling or advanced routing. Workers need the same
models and settings as the API (shared HF cache volume in compose).
