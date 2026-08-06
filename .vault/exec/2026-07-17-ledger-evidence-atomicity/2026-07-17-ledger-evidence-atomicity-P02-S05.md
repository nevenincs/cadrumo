---
tags:
  - '#exec'
  - '#ledger-evidence-atomicity'
date: '2026-07-17'
modified: '2026-07-19'
body_hash: 'sha256:c719e65b0a30f3a88eb1156217ef581a5737e88d4a724e63f6d1508f8a0b264e'
step_id: 'S05'
related:
  - "[[2026-07-17-ledger-evidence-atomicity-plan]]"
---

# Prove every LLM split child inherits the parent evidence and provenance consistently and any child validation or persistence failure leaves the parent, children, catalogue, and event history unchanged

## Scope

- `src/cadrumo/application/ledger/tests/test_llm_evidence_split_apply.py`

## Description

- Add `test_split_children_retain_lineage_and_evidence_provenance`: after an evidence-driven split, prove the parent is SPLIT with a PARENT `split_lineage`, and every child is BUSINESS-classified, carries a CHILD `split_lineage` bound to the same split group and citing the parent as a sibling, inherits the parent's `purchase_invoice_evidence_id`, and carries an `evidence_provenance` entry for it.
- Add `test_split_child_evidence_failure_leaves_everything_unchanged`: seed a parent citing a nonexistent evidence record so the atomic writer's per-child evidence validation fails; prove `apply_evidence_split` raises, the parent stays ACTIVE with no `split_lineage`, only the parent row exists, and the event history equals its pre-call snapshot.

## Outcome

- Consistent inheritance and atomicity proven with real secure storage, real repositories, real bucket-event history, and a real subprocess LLM proposer — no mocks/stubs. The forced failure is genuine (missing evidence record), not injected.
- The lineage-retention assertion pins the P02.S04 fix for the previously-dropped child `split_lineage`.
- `test_llm_evidence_split_apply.py`: 5 passed. Full ledger application suite 384 passed. Ruff clean. Commit `6d6c33f5ba`.

## Notes

- None.
