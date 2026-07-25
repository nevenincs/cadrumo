---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S224'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Make evidence-driven LLM splitting persist the parent transition, every child, inherited validated evidence links, provenance, classifications, and events in one atomic application transaction without generic field patching

## Scope

- `src/cadrumo/application/ledger/_actions_split_merge.py`
- `src/cadrumo/application/ledger/_llm_classification.py`

## Description

This Step is already satisfied at HEAD; the record documents the landed state verified against HEAD. The predecessor ledger-evidence-atomicity campaign landed the writer in commit `8120535d40`, hardened by `b3d8ab6b76`.

- Extract the in-memory split build out of `split_transaction` into a helper returning the parent transition, the bare child rows, the split event, the split group id, and the child ids without persisting anything.
- Add `split_transaction_with_classified_children` in `_actions_split_merge.py` as the atomic evidence-driven split writer: it builds the split state, then per child derives a classification command from that child's patch and runs the in-memory update builder, which validates the inherited evidence references and constructs the provenance entries and audit events.
- Restore each child's split lineage onto the rebuilt row inside the same write, closing a latent defect in the former split-then-patch route which rebuilt the child from a command and silently dropped its lineage.
- Refuse a per-child classification patch that alters a raw movement field, because the child id is content-addressed over the raw movement and a changed id would strand siblings, lineage, and the returned result on a stale id.
- Persist the parent transition, every classified evidence-bearing child, and the split plus per-child events with one catalogue-and-events save.
- Rewire `apply_evidence_split` in `_llm_classification.py` onto the atomic writer and build each child's classification and inherited-evidence patch, removing the split-then-per-child generic patch loop.

## Outcome

The evidence-driven split no longer re-enters evidence through the generic patch door, so it does not need and does not take the evidence-authority escape. There is no longer a window in which a child exists split but unclassified or evidence-less. Atomicity holds structurally: parent resolution, amount validation, the child id guard, and every child's evidence validation all run before the single save, so any failure raises with nothing persisted.

Verified against HEAD by inspection of both scoped files and by the sibling Step's gates; the wider `uv run --no-sync pytest -m "" src/cadrumo/application/ledger/tests/` run reports 427 passed and full-tree collection is clean.

## Notes

The plan row for the predecessor campaign named a split-persistence module that does not exist in the tree; this plan row correctly names `_actions_split_merge.py`, which is where the writer lives at HEAD. The in-memory update builder writes a self-referential edit-lineage entry per child, matching the prior split-then-patch behaviour; that is intentional parity, not a regression.
