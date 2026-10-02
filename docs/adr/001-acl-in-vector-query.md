# ADR-001: Enforce document ACLs inside the vector query

**Status:** accepted

**Context.** A RAG system leaks data if retrieval returns chunks the user may not read: the LLM can then quote them. The common
shortcut is to retrieve top-k and filter afterwards, which also silently shrinks recall (the top-k can be all forbidden chunks).

**Decision.** Store `tenant_id`, `visibility`, `owner_id` and `group_ids` as payload on every chunk and apply them as a Qdrant
filter in the query itself. Add a second, independent check: after retrieval, re-authorize the distinct document ids against Postgres
before generation.

**Consequences.** Forbidden chunks are never retrieved and recall is computed over the allowed set only. Permission changes must
update both Postgres and vector payload (`update_acl`). The same rule exists in SQL, Qdrant and Python; a test enumerates every
tenant/visibility/owner/group combination to prove the three agree. The DB guard costs one indexed query per request.

**Rejected.** Collection-per-document (does not scale), post-filtering only (leaks and hurts recall).
