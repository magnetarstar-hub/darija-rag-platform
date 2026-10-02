# ADR-002: Postgres for state, Qdrant for vectors

**Status:** accepted

**Context.** pgvector would give one datastore and transactional ACL updates. Qdrant gives payload-indexed filtered ANN search,
simple horizontal scaling and an embedded mode that makes tests hermetic.

**Decision.** Postgres is the source of truth (tenants, users, groups, documents, ACLs, audit). Qdrant holds only derived data
that can be rebuilt from stored files (idempotent `process_document`).

**Consequences.** Two stores can drift; mitigated by ADR-001's DB guard and idempotent re-ingestion. Tests run the real Qdrant
filter logic in `:memory:` mode with no server. Revisit pgvector if operational simplicity outweighs filtered-search performance.
