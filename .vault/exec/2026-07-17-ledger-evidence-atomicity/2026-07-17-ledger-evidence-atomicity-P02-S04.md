---
tags:
  - '#exec'
  - '#ledger-evidence-atomicity'
date: '2026-07-17'
modified: '2026-07-19'
step_id: 'S04'
related:
  - "[[2026-07-17-ledger-evidence-atomicity-plan]]"
---

# Make evidence-driven LLM splitting persist the parent transition, every child, inherited validated evidence links, provenance, classifications, and events in one atomic application transaction without generic field patching

## Scope

- `src/cadrumo/application/ledger/_actions_split_manual.py`

## Description

- Extract `split_transaction`'s in-memory build into `_build_split_state`, returning the parent transition, child rows, split event, group id, and child ids without persisting; `split_transaction` keeps its behaviour, calling the helper then saving.
- Add `split_transaction_with_classified_children`: the atomic evidence-driven split writer. It builds the split state, then for each child derives the classification command from a per-child patch and runs `_prepare_manual_transaction_update` (which validates inherited evidence and builds provenance + events) in memory, restoring the child's `split_lineage`, then persists parent transition + every classified evidence-bearing child + all events in ONE `_save_transaction_catalogue_and_events`.
- Rewire `apply_evidence_split` onto the atomic writer; add `_split_child_patch_fields` to build each child's classification+evidence patch. Remove the split-then-per-child-`update_manual_transaction_fields` loop.
- Export `split_transaction_with_classified_children` from the ledger facade.

## Outcome

- The evidence-driven split no longer re-enters evidence through the generic patch door and no longer leaves a window in which a child is split-but-unclassified/evidence-less. It also fixes a latent bug: the old split-then-patch path rebuilt each child from a command and silently dropped its `split_lineage`; the atomic writer restores lineage in the same write.
- Atomicity holds structurally: parent resolution, amount validation, and every child's evidence validation run before the single save; a failure raises with nothing persisted.
- The plan names `_actions_split_manual.py`; the actual split-persistence module is `_actions_split_merge.py` (there is no `_actions_split_manual.py`) — the writer landed there.
- Files: `_actions_split_merge.py`, `_llm_classification.py`, `__init__.py`. Full ledger application suite 384 passed; CLI classify/split/lifecycle green; ruff + collect-only clean. Commit `8120535d40`.

## Notes

- `_prepare_manual_transaction_update` writes a self-referential `edit_lineage` entry per child (previous_transaction_id == child id); this matches the prior split-then-patch behaviour and is intentional parity, not a regression.
