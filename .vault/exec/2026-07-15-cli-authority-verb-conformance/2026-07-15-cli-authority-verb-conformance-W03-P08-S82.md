---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
body_hash: 'sha256:e60b035b7d7e3486bc02c061e4435d71ac93892f62d210be631913b440dec53b'
step_id: 'S82'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Prove direct evidence patches fail, invoice linkage cannot mutate evidence, and failed attach or link leaves transaction, evidence catalogue, provenance, and event history unchanged

## Scope

- `src/cadrumo/application/ledger/tests/test_actions_update_evidence.py`

## Description

This Step is already satisfied at HEAD; the record documents the landed state verified against HEAD. The predecessor ledger-evidence-atomicity campaign landed the gate in commit `9296e3ebd2`, extended by `b3d8ab6b76` and `a7d8f8aa38`.

- Prove the attach authority is the working evidence door: attaching purchase evidence persists the link and emits the attach event.
- Prove the generic command door refuses a direct evidence change, and prove the generic patch door refuses a patch that sets either reserved evidence field.
- Prove a generic field edit preserves the existing evidence link rather than silently dropping it.
- Prove the bulk classify column allowlist and the reserved evidence axis are disjoint, closing the one path that reaches the update builder below the wrapper guard.
- Prove invoice linkage cannot mutate evidence: after a link the stored purchase evidence id is unchanged and the event history differs only by the single linkage audit event.
- Prove a failed attach leaves the transaction, its evidence link, its provenance tuple, and the event history unchanged, by naming an evidence id no record backs.
- Prove a failed invoice link leaves the transaction and the event history unchanged, by naming an invoice absent from the catalogue.

## Outcome

The bypass-impossible and atomicity claims are proven through real behaviour: every test drives the real encrypted secure-object repository, the real transaction and invoice catalogue repositories, and the real bucket event history. The refusals are asserted structurally by exception type and by field names carried in the error, never against localized prose. The failure proofs induce a genuine error path and then read the persisted state back, so a partial write would surface as a changed transaction, a non-empty provenance tuple, or an extra event.

Gate: `uv run --no-sync pytest -m "" src/cadrumo/application/ledger/tests/test_actions_update_evidence.py` reports 8 passed.

## Notes

The invoice-linkage proof asserts the event history is identical either side once the single linkage event is projected out, rather than asserting a bare count. That distinguishes an unchanged evidence history from a history that merely happens to have the same length.
