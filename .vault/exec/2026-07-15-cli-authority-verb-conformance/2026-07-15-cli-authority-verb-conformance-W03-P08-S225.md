---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
body_hash: 'sha256:1be8be7b8793c9766224120cbd6fba1ced092099798c7f35c152b952cba475da'
step_id: 'S225'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Prove every LLM split child inherits the parent evidence and provenance consistently and any child validation or persistence failure leaves the parent, children, catalogue, and event history unchanged

## Scope

- `src/cadrumo/application/ledger/tests/test_llm_evidence_split_apply.py`
- `src/cadrumo/application/ledger/tests/test_llm_evidence_split.py`

## Description

This Step is already satisfied at HEAD; the record documents the landed state verified against HEAD. The predecessor ledger-evidence-atomicity campaign landed the gates in commits `6d6c33f5ba` and `58497dc90a`.

- Prove the applied split transitions the parent to the split lifecycle state and classifies every child.
- Prove each child inherits the parent's purchase evidence id, and that the inherited id also appears in that child's evidence provenance entries, so the link and its provenance stay consistent.
- Prove each child carries split lineage in the child role, bound to the returned split group id and naming the parent among its siblings, in the same write as the classification.
- Prove child amounts and each child's tax substrate are registry-derived rather than model-supplied.
- Prove a child evidence-validation failure leaves everything unchanged: seed a parent whose evidence id backs no record, apply the split, and assert the parent is still active with null split lineage, that the catalogue holds only the parent row, and that the event history equals its pre-attempt value.
- Prove a per-child classification patch that re-addresses the child id is refused before any write, leaving the parent active and the catalogue single-rowed.

## Outcome

Child evidence and provenance inheritance is proven consistent, and the atomicity claim is proven by inducing two genuinely different real failure paths: a missing evidence record surfacing from the shared reference validator, and a raw-field patch tripping the content-addressed child id guard. Both proofs read back the persisted catalogue and the persisted event history and assert equality with the pre-attempt state, so a partial write would surface as an extra row or an extra event rather than passing silently.

Gates: `uv run --no-sync pytest -m "" src/cadrumo/application/ledger/tests/test_llm_evidence_split_apply.py` reports 6 passed and `uv run --no-sync pytest -m "" src/cadrumo/application/ledger/tests/test_llm_evidence_split.py` reports 3 passed.

## Notes

The suggestion side of the split is driven through the real proposer seam with a canned proposal payload, so the model is not called while the persistence path under test stays entirely real. No test double stands in for a repository, an attachment store, or the event history.
