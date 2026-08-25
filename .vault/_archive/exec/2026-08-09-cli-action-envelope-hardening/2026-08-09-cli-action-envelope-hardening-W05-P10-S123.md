---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:ff61824d9c2e92d0c7084a8b56fb1e2e793e27902cb697299607f5c5fd33733a'
step_id: 'S123'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---
# Migrate Google calculation-sheet refusals to typed outcomes

## Scope

- `src/cadrumo/adapters/outbound/google/_calc_sheets_apply.py`
- `src/cadrumo/adapters/outbound/google/_calc_sheets_pull.py`
- Direct calculation-sheet tests

## Description

Migrated all reachable apply and pull transport, state-divergence, identifier, edit-value, casilla-input, metadata, snapshot, and reference refusals to exact typed terminal outcomes.

## Outcome

- External client and transport failures declare safety outcomes.
- Ownership, provider-contract, synchronization, malformed edit, and undeclared-input conditions declare operator-decision outcomes without invented actions.
- Every distinct terminal family is tested against exact condition/evidence identity, runtime provenance, complete facts, no action or bindings, and not-applicable conditionality.
- Registry-dependent snapshot proof was replaced with an isolated minimal real-model snapshot.
- Verification: focused non-registry suite — 21 passed; ruff and diff checks — clean.
- Independent review: PASS.

## Notes

Shared verdict assembly is owned by the separately reviewed canonicalization step `S124`.
