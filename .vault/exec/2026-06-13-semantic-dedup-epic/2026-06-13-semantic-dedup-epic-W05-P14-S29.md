---
tags:
  - '#exec'
  - '#semantic-dedup-epic'
date: '2026-06-14'
modified: '2026-06-15'
step_id: 'S29'
related:
  - "[[2026-06-13-semantic-dedup-epic-plan]]"
---




# C5-1 Extract a shared content-hash verify kernel and route the two storage backends through it

## Scope

- `src/aeat/adapters/outbound/storage/_local.py`

## Description

- Re-read both verify sites (post C1-1b sweep, which had already moved them to
  `sha256_hex`) and confirmed the genuine gating divergence: local verifies any
  non-empty stored digest; Drive only a full 64-char digest.
- Created `outbound/storage/_integrity.py` with `strip_sha256_prefix` and
  `verify_content_hash(actual_hash, stored_hash, *, message, context,
  translated_message, require_full_digest=False)`.
- Routed both backends through it: local with `require_full_digest=False`
  (still computing `actual_hash` itself, reused to stamp the written sidecar),
  Drive with `require_full_digest=True`.
- Regenerated the API stub for the new module (`apidocs scaffold`).

## Outcome

Committed as the C5-1 commit, tagged `relocation:verify_content_hash` (5 files
incl. 2 doc stubs). Ruff clean; 69 outbound-storage tests green; apidocs
`scaffold --check` conformant.

## Notes

The kernel takes a precomputed `actual_hash` rather than the payload because
the local backend reuses the digest after the check (to build the
`content_hash` sidecar value); the `require_full_digest` flag preserves the two
backends' distinct verification policies exactly. The local mismatch message
was trimmed (the stored/actual values remain in `context`) to satisfy the
120-char line limit; no test asserts that message string.
