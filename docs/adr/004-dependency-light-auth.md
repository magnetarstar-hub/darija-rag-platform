# ADR-004: Stdlib scrypt + PyJWT, no auth framework

**Status:** accepted (revisit for SSO)

**Decision.** Passwords use `hashlib.scrypt` (memory-hard, stdlib, constant-time compare). Tokens are short-lived HS256 JWTs with
`sub`, `tid`, `role`. The user row is re-read on every request, so the token only proves identity, never current privileges.

**Consequences.** Small attack surface and few dependencies; no refresh tokens, MFA or SSO yet. Enterprise customers would
normally require OIDC: planned in the roadmap, and the `current_user` dependency is the single place to swap.
