# Security notes and known limits

Be explicit about what this does **not** do:

- **Rate limiting is per process** (in-memory). With several API replicas the effective limit multiplies; use a Redis-backed limiter.
- **JWTs are stateless for up to `RAG_JWT_EXPIRE_MINUTES`**, but every request re-loads the user, so deactivation, role and group changes
  take effect immediately. There is no refresh-token flow or revocation list yet.
- **Prompt-injection screening is pattern-based.** It catches common phrasings in EN/FR/AR, not adversarial paraphrases. The
  defense that matters is structural: sources are untrusted, the model has no tools, and answers must cite sources and pass the verifier.
- **The verifier is an LLM.** It reduces, but does not eliminate, ungrounded answers. Measure it on your own data.
- **No encryption at rest** is configured for uploads, Postgres or Qdrant; rely on volume/disk encryption in your environment.
- **TLS is not terminated here**; put the API behind a reverse proxy/ingress.
- **Email is globally unique** (a person belongs to one tenant).
- **Single-writer embedded Qdrant** is for dev only. Production uses the Qdrant server (`RAG_QDRANT_URL`).
- **No malware scanning** of uploads.
