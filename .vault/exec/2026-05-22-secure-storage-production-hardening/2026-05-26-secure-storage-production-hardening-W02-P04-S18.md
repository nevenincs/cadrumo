---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-05-26'
modified: '2026-05-26'
step_id: 'S18'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-05-26-secure-storage-production-hardening-w02-p04-s18-review-audit]]'
---

# `secure-storage-production-hardening` `W02.P04.S18`

Enrolled auth session and outbound adapter repositories in runtime-created secure storage.

- Modified: `src/aeat/adapters/outbound/aeat/auth/_session_store.py`
- Modified: `src/aeat/adapters/outbound/google/_session_store.py`
- Modified: `src/aeat/adapters/outbound/llm/_cache.py`
- Modified: `src/aeat/adapters/outbound/llm/_usage.py`
- Modified: `src/aeat/adapters/outbound/aeat/sede/_observation_store.py`
- Modified: focused active-runtime tests for auth, Google, LLM, Sede observation, registry verification, and declaration observation binding.

## Description

The adapter persistence defaults now resolve through the active profile bucket runtime instead of constructing physical secure-object repositories directly. Auth browser sessions, Google OAuth/Drive configuration records, LLM cache entries, LLM usage records, and Sede filed/IVA observation stores all use active-bucket repository factories when no repository is explicitly injected.

The Sede observation store preserves explicit repository injection but no longer opens its own provider-owned crypto/session scope. Tests that previously relied on explicit database URLs or provider-only storage setup now enter `override_settings(aeat_local_storage_root=..., aeat_active_profile=...)` and a real `BucketSession` so they exercise the same runtime route as production.

## Tests

- `uv run ruff check` on the S18 implementation and focused tests: passed.
- `uv run pytest` S18 focused bundle: `55 passed`.
- `uv run python -m aeat.locales audit`: `ca.yml`, `en.yml`, `es.yml`, and `hu.yml` ok.
- Code review recorded in `2026-05-26-secure-storage-production-hardening-W02-P04-S18-review-audit.md`; re-review found no remaining HIGH or CRITICAL issues.
