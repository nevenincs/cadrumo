---
tags:
  - '#exec'
  - '#import-centralization'
date: '2026-07-02'
modified: '2026-07-17'
step_id: 'S49'
related:
  - "[[2026-07-01-import-centralization-plan]]"
---

# Rewire 5 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.modelos`

## Scope

- `src/aeat/application/modelo/__init__.py`

## Description

Ran the `dev/import_centralization_codemod.py` AST codemod against every production `aeat.application.modelo` module, rewriting every cross-package private import onto the owning package's promoted top-level facade. This record anchors and covers the entire `W02.P36` Phase (47 files, all `aeat.application.modelo` production consumer sites) in one commit, per the batching directive for this Wave.

- Ran the codemod in dry-run, then `--apply`, over the full `src/aeat` tree.
- Normalised the rewritten import blocks with `ruff check --fix --select I` and `ruff format`.
- Verified `pytest --collect-only -q src/aeat` collected cleanly (0 import errors attributable to this batch).
- Committed the 47 `aeat.application.modelo` files as one atomic explicit-pathspec commit.

## Outcome

47 files rewritten and committed (commit `01ec29a3e`, `refactor(application.modelo): route cross-package imports through owning facade (import-centralization W02)`). Every `aeat.application.modelo` production `ImportFrom` statement that reached a foreign package's private submodule now imports from that package's `__all__` facade. Behavior-preserving: no symbol relocation, no signature change.

## Notes

Steps `W02.P36.S49` through `W02.P36.S96` (the full Phase) are covered by this one record and this one commit, batched per the Wave dispatch brief rather than scaffolded individually — 250 W02 Steps at one-record-each was not proportionate to the session's remaining budget. Plan checkboxes for the covered Steps are left unchecked pending a follow-up bulk `vault plan step check` pass; the commit SHA above is the durable evidence trail.
