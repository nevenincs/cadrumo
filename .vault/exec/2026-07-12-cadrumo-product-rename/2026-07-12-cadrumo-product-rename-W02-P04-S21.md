---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-17'
body_hash: 'sha256:0350c65717257cc031f211523df4618f26771aa2e906a616b8fa1784fa057811'
step_id: 'S21'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# Rename product logical storage namespaces without touching authority field names

## Scope

- `src/cadrumo persistence namespace registry/repository and cohesive consumers/tests/examples`

## Description

- Rename all 67 registered logical storage namespaces and owners to the Cadrumo product prefixes.
- Preserve the six internal `.aeat.` authority segments that identify the external tax authority.
- Reject former product namespaces centrally before namespace-scoped read, write, delete, list, and batch operations.
- Update cohesive runtime consumers and real-behavior storage tests.

## Outcome

- Cut over 61 ordinary registry rows and six mixed-authority rows without compatibility aliases or fallback paths.
- Added a single former-product-prefix admission boundary with explicit validation context.
- Verified five focused tests in an isolated filesystem mirror, covering the 67-row invariant, refusal without storage mutation, and batch behavior.

## Notes

- A broader 29-test mirror probe produced 28 passes and one unchanged pre-existing discovery assertion failure for `cadrumo.domain.transactions.bucket`; the focused S21 proof passes.
- The mirror setup reported a missing optional `.env.example`; this did not affect the test run.
