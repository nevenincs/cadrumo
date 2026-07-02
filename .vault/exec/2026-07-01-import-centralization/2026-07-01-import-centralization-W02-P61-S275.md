---
tags:
  - '#exec'
  - '#import-centralization'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S275'
related:
  - "[[2026-07-01-import-centralization-plan]]"
---

# Rewire 5 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.calculations.registry`

## Scope

- `src/aeat/domain/modelos/_calculation_revision.py`

## Description

Ran the `dev/import_centralization_codemod.py` AST codemod against every production `aeat.domain.modelos`, `aeat.domain.transactions`, `aeat.domain.attachments`, `aeat.domain.deadlines`, `aeat.domain.fincas`, `aeat.domain.invoices`, and `aeat.domain.iva` module, rewriting every cross-package private import onto the owning package's promoted top-level facade. This record anchors and covers Phases `W02.P60`, `W02.P61`, `W02.P62`, `W02.P76`-`W02.P79` in one commit, per the batching directive for this Wave.

- Ran the codemod in dry-run, then `--apply`, over the full `src/aeat` tree.
- Normalised the rewritten import blocks with `ruff check --fix --select I` and `ruff format`.
- Verified `pytest --collect-only -q src/aeat` collected cleanly (0 import errors attributable to this batch).
- Committed the 9 files as one atomic explicit-pathspec commit.

## Outcome

9 files rewritten and committed (commit `1f292b29a`, `refactor(domain): route cross-package imports through owning facade (import-centralization W02)`). Behavior-preserving: no symbol relocation, no signature change.

## Notes

Steps across `W02.P60`-`W02.P62` and `W02.P76`-`W02.P79` are covered by this one record and this one commit, batched per the Wave dispatch brief. This was the final W02 batch: the import-hygiene scanner's post-batch run reported 0 production sites needing facade promotion and only the 5 documented cycle-break exceptions (`application/review/_actions.py`, `application/review/_models.py`, `application/workflow/_models.py`) remaining unrewritten. Plan checkboxes for the covered Steps are left unchecked pending a follow-up bulk `vault plan step check` pass; the commit SHA above is the durable evidence trail.
