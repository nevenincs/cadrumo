---
tags:
  - '#exec'
  - '#ledger-evidence-atomicity'
date: '2026-07-17'
modified: '2026-07-19'
body_hash: 'sha256:9b557aa43df6079623b5a429f98ab76bbbc5386614f033601dcfe13eeb6f4ac9'
step_id: 'S17'
related:
  - "[[2026-07-17-ledger-evidence-atomicity-plan]]"
---

# Add an explicit id-stability assertion to split_transaction_with_classified_children that raises when a classified replacement child transaction_id diverges from the bare child it derives from, so a divergence cannot silently misattribute evidence and provenance, gated on a test proving the split raises on a mismatched replacement transaction_id rather than proceeding

## Scope

- `src/cadrumo/application/ledger/_actions_split_merge.py`

## Description

- Add the id-stability assertion inside `split_transaction_with_classified_children`: after building each classified replacement child, raise `TransactionValidationError` if `replacement.transaction_id != bare_child.transaction_id` (landed in commit `b3d8ab6b76`).
- Add `test_split_child_classification_that_changes_raw_id_is_refused`: call the atomic writer directly with a per-child classification patch that alters a raw movement field (amount), and prove it raises before any persistence — the parent stays ACTIVE and only the parent row exists (commit `58497dc90a`).

## Outcome

- A classification patch that would re-address a child under a new content id can no longer silently misattribute evidence/provenance to a stale sibling id; the atomic writer refuses and persists nothing. `test_llm_evidence_split_apply.py`: 6 passed.

## Notes

- The raise is unreachable through the live `apply_evidence_split` path (its patches never carry raw fields), so the test drives the writer directly with a raw-field patch to exercise the guard — the reviewer's requested proof that the guard bites.
