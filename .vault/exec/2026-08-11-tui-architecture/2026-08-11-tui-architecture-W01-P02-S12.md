---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:8d1c098baf3ffddfd0fb427ca5ebd68951338b1001f6eca63742310d8a76fe4f'
step_id: 'S12'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---
# Prove state-axis independence, capability validation, exact response binding, and event redaction invariants

## Scope

- `src/cadrumo/application/operations/tests/test_contract_invariants.py`

## Description

- Re-ground cross-contract acceptance invariants through live code/vault RAG, accepted ADR/plan, whole S06-S11 owners, and targeted searches.
- Exercise only public `application.operations` production contracts without mirroring validators.
- Plant combinatorial nonterminal/terminal axis models, invalid terminal correlations, every production capability-validator family, exact response tuple preservation, and sensitive diagnostic-reference mutations.

## Outcome

- Every declared nonterminal lifecycle is independently representable across every effect, and every terminal condition is independently representable across every effect; production snapshots refuse nonterminal terminal facts and receipt-effect drift.
- Each capability-validator branch is exercised from a production-valid base with exactly one mutated field, covering ephemeral replay/conflict/effect, empty effects, resumability symmetry in both directions, durable conflict scope, contained-resource ownership, unsupported cancellation with cooperative deadline, unsupported cancellation with request-cancel close policy, and enforced deadline without containment.
- APPLY round-trips its exact binding tuple. Fresh RAG and exact `rg` found no production correlation comparator yet: S10 owns immutable evidence shape, while S22 supervisor response consumption owns comparison and single-use state. S12 therefore does not invent comparison business logic or falsely claim lexically valid wrong identities can be rejected without an expected interaction.
- Raw NIF, bearer, URL/query, and exception-like diagnostic material is refused through the public event boundary.
- Focused gates passed: pytest reported `69 passed in 4.53s`; Ruff reported `All checks passed!`; basedpyright reported `0 errors, 0 warnings, 0 notes`.

## Notes

- Live semantic searches succeeded; targeted inspection confirmed the tests consume the public facade and do not redeclare production business logic.
- Final review passed and the binding row was CLI-closed. `vault check all` exited zero with `1338 warnings`, including 6 annotation, 22 markdown, 29 schema, 3 modified-stamp, and pre-existing body-schema corpus warnings.
