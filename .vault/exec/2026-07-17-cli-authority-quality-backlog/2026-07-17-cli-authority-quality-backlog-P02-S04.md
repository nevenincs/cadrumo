---
tags:
  - '#exec'
  - '#cli-authority-quality-backlog'
date: '2026-07-17'
modified: '2026-07-19'
step_id: 'S04'
related:
  - "[[2026-07-17-cli-authority-quality-backlog-plan]]"
---

# Add an AST recurrence gate that rejects new reducible production SHA-256 constructor and one-shot hexdigest bodies while allowing streaming, HMAC, HKDF, X509, and digest-byte uses

## Scope

- `src/cadrumo/core/tests/test_hashing_adoption.py`

## Description

- Add the new `test_hashing_adoption.py` recurrence gate under `core/tests/`.
- Add the AST detector `_reducible_one_shot_sites`: flags `sha256(<data>).hexdigest()` — a one-shot constructor with at least one positional arg, immediately hex-digested (a trailing slice like `[:16]` stays reducible). It never flags an argument-free `sha256()` fed incrementally via `.update()`, a `.digest()` raw-bytes use, or `hmac.new(..., sha256).hexdigest()` and other keyed/derived constructors.
- Pin `_REDUCIBLE_ONE_SHOT_BASELINE`: the 24 grandfathered reducible bodies across 23 production modules (captured from the current tree; the canonical helper `core/hashing.py` is excluded as the reduction target).
- Add `test_no_new_reducible_one_shot_sha256_body_lands`: an additions-only ratchet asserting no new module and no grandfathered module gains a reducible one-shot body beyond its baseline; delegating an existing body to `core.hashing.sha256_hex` (lowering a count) is always allowed.
- Add `test_recurrence_baseline_is_grounded_in_real_sites`: fails only if a baseline module drops to zero reducible bodies, so a fully-stale entry that would silence the ratchet is surfaced.

## Outcome

The gate prevents a NEW reducible one-shot SHA-256 body from landing while leaving streaming, HMAC, HKDF, X509, and digest-byte uses untouched — the ADR's decision to stop rewriting the existing bodies (low-value churn against a service that already exists) and instead lock the recurrence surface. Additions-only design is robust to the churning tree: a peer reducing a body lowers a count without falsely reddening the gate. 3 tests pass; ruff clean; collection clean.

## Notes

No production code changed — the ADR explicitly does not rewrite the 24 grandfathered bodies. Churn caveat: two baseline modules (`application/auth/_operator.py`, `_certificate_sources_operator.py`) are on the live auth-cert cutover surface; if that cutover removes their only reducible body, the grounding test will ask for the stale entry to be dropped (a one-line fix), never a false pass. The discrimination proof for this gate is recorded under `S05`.
