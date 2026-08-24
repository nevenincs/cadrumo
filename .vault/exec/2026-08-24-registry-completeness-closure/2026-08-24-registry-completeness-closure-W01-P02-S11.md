---
tags:
  - '#exec'
  - '#registry-completeness-closure'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:690604f9cfe196080fdc05af9d5b321f1e856ec9332fb31fdc1f59c6546ad204'
step_id: 'S11'
related:
  - "[[2026-08-24-registry-completeness-closure-plan]]"
---

# Prove complete, refused, stale-evidence, below-filing-grade, and cross-limb disagreement outcomes with mutation tests

## Scope

- `src/cadrumo/application/registry/tests/`

## Description

- Replace the test-time `os.open` monkeypatch with an actual in-repository symlink substitution.
- Preserve the descriptor/path-identity refusal through the production digest verifier.
- Re-run the application registry and closure-predicate outcome matrices.

## Outcome

The source-connectivity descriptor-substitution mutation now uses real filesystem behavior and is rejected without a patch, mock, skip, xfail, or ratchet-baseline change. The full application registry suite passed 152 tests; the source-contract module passed 23 tests; the cross-authority closure suite passed 8 tests; and Ruff passed on the changed module. Independent review found no scoped findings.

## Notes

The global monkeypatch inventory remains red only for independently owned user-profile and CLI configuration tests. Its report no longer names this registry test.
