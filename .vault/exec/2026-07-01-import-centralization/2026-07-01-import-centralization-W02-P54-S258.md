---
tags:
  - '#exec'
  - '#import-centralization'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S258'
related:
  - "[[2026-07-01-import-centralization-plan]]"
---

# Rewire 1 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.core.errors`

## Scope

- `src/aeat/core/resources/_errors.py`

## Description

Ran the `dev/import_centralization_codemod.py` AST codemod against every production `aeat.core.resources`, `aeat.core.observability`, `aeat.core.config`, `aeat.core.corpus_manifest`, `aeat.core.json_contract`, `aeat.core.logging`, and `aeat.locales._fstring_registry` module, rewriting every cross-package private import onto the owning package's promoted top-level facade. This record anchors and covers Phases `W02.P54`, `W02.P59`, `W02.P72` through `W02.P75`, and `W02.P81` in one commit, per the batching directive for this Wave.

- Ran the codemod in dry-run, then `--apply`, over the full `src/aeat` tree.
- Normalised the rewritten import blocks with `ruff check --fix --select I` and `ruff format`.
- Verified `pytest --collect-only -q src/aeat` collected cleanly (0 import errors attributable to this batch).
- Committed the 10 files as one atomic explicit-pathspec commit.

## Outcome

10 files rewritten and committed (commit `563dece0e`, `refactor(core,locales): route cross-package imports through owning facade (import-centralization W02)`). Behavior-preserving: no symbol relocation, no signature change.

## Notes

Steps across `W02.P54`, `W02.P59`, `W02.P72`-`W02.P75`, and `W02.P81` are covered by this one record and this one commit, batched per the Wave dispatch brief. Plan checkboxes for the covered Steps are left unchecked pending a follow-up bulk `vault plan step check` pass; the commit SHA above is the durable evidence trail.
