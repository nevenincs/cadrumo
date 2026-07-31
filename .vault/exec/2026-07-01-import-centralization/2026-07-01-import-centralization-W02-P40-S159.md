---
tags:
  - '#exec'
  - '#import-centralization'
date: '2026-07-02'
modified: '2026-07-17'
body_hash: 'sha256:343ee0e80c3a2f8b6bbcbf0e41c26274aef82f349f9edcacbdf6a65e32cd7f68'
step_id: 'S159'
related:
  - "[[2026-07-01-import-centralization-plan]]"
---

# Rewire 5 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.buckets`, `aeat.domain.modelos`, `aeat.domain.transactions`

## Scope

- `src/aeat/application/ledger/_actions_classification.py`

## Description

Ran the `dev/import_centralization_codemod.py` AST codemod against every production `aeat.application.ledger` module, rewriting every cross-package private import onto the owning package's promoted top-level facade. This record anchors and covers the entire `W02.P40` Phase in one commit, per the batching directive for this Wave.

- Ran the codemod in dry-run, then `--apply`, over the full `src/aeat` tree.
- Normalised the rewritten import blocks with `ruff check --fix --select I` and `ruff format`.
- Verified `pytest --collect-only -q src/aeat` collected cleanly (0 import errors attributable to this batch).
- Committed the 16 `aeat.application.ledger` files as one atomic explicit-pathspec commit.

## Outcome

16 files rewritten and committed (commit `3a83394c6`, `refactor(application.ledger): route cross-package imports through owning facade (import-centralization W02)`). Behavior-preserving: no symbol relocation, no signature change.

## Notes

The full `W02.P40` Phase is covered by this one record and this one commit, batched per the Wave dispatch brief. Plan checkboxes for the covered Steps are left unchecked pending a follow-up bulk `vault plan step check` pass; the commit SHA above is the durable evidence trail.
