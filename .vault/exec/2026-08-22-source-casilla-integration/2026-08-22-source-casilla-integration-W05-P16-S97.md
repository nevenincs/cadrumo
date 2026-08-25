---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:1b9ca2f4b65e2f744e4f1d812a6110c8baf004daef0963889df404f58f082a34'
step_id: 'S97'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

# retain the M360 refund-operation ingress-blocked census disposition and permit reopening only after one secure owner retains the full official request/document carrier with durable identity and fingerprint and S98 proves encrypted persistence/replay diagnostics/review and supported repeated-record export

## Scope

- `src/cadrumo/_data/source_connectivity/census.toml`
- `dev/source_connectivity/tests/test_m360_deferral.py`

## Description

- Amend S97 through the plan CLI from impossible resolver enrollment to the evidence-backed bounded deferral.
- Retain the canonical M360 census row as `ingress_blocked` with an explicit owner, expiry, and owned follow-up.
- State the exact reopening predicate: complete official carrier, immutable durable identity and fingerprint, secure owner, and S98 proof.
- Bind the predicate and absence of resolver, connected proof, and repeated-record lifecycle with the focused census test.

## Outcome

Modelo 360 remains explicitly deferred. No resolver or M360 calculation semantics were introduced. Reopening is possible only after every evidence-backed carrier and proof condition is met.

## Notes

- The first predicate exceeded the census model's 500-character limit; it was shortened without dropping a required official axis.
- Focused pytest passed: `dev/source_connectivity/tests/test_m360_deferral.py` (3 passed). Focused Ruff passed.
- The feature-scoped vault check reported no errors; its remaining warnings are pre-existing feature reference/template hygiene.
- Formal self-review audit was intentionally excluded by the authorized S97 scope.
