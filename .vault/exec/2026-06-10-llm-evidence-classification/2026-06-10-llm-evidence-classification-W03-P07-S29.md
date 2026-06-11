---
tags:
  - '#exec'
  - '#llm-evidence-classification'
date: '2026-06-10'
step_id: 'S29'
related:
  - "[[2026-06-10-llm-evidence-classification-plan]]"
---




# Add split-invariant, registry-derived-number, and per-child provenance roundtrip tests

## Scope

- `src/aeat/application/ledger/tests/test_llm_evidence_split.py`
- `src/aeat/entrypoints/cli/tests/test_ledger_llm_split.py`

## Description

- Application-layer real-behaviour tests (6) against real SQLite persistence with an injected in-process proposer: child amounts sum exactly to the parent; each child's `base + iva` reconstitutes its magnitude at the registry 0.21; the parent invoice links to every child; the persisted child state survives a save/load roundtrip; the children's numbers are registry-derived, not model-emitted.
- CLI integration tests (4) drive `aeat app ledger split --llm` end to end: suggest previews derived amounts and persists nothing; apply persists the split + classified children; `--apply` without `--yes` and `--llm` with manual child flags are refused.

## Outcome

Commits `a9b654ed9` (application) + `d34bcd736` (CLI). All 10 tests green; allowlisted the new test→adapter/secure_sql edges in `.importlinter`.

## Notes

No mocks, skips, or tautological assertions: determinism is dependency injection (application) and a registered in-process proposer (CLI).
