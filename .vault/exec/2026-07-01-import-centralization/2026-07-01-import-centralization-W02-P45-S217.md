---
tags:
  - '#exec'
  - '#import-centralization'
date: '2026-07-02'
modified: '2026-07-17'
step_id: 'S217'
related:
  - "[[2026-07-01-import-centralization-plan]]"
---

# Rewire 1 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.core.time`

## Scope

- `src/aeat/application/auth/_acquisition_lock.py`

## Description

Ran the `dev/import_centralization_codemod.py` AST codemod against every production `aeat.application.auth`, `aeat.application.filing`, `aeat.application.overview`, `aeat.application.wizard`, `aeat.application.review`, and `aeat.application.workflow` module, rewriting every cross-package private import onto the owning package's promoted top-level facade. This record anchors and covers Phases `W02.P45` through `W02.P48`, `W02.P51`, and `W02.P52` in one commit, per the batching directive for this Wave.

- Ran the codemod in dry-run, then `--apply`, over the full `src/aeat` tree.
- Discovered and fixed a genuine `ImportError` regression: the codemod's facade rewrite of `application/review/_actions.py` and `application/review/_models.py` (from `..workflow._models` / `..workflow._utils` to `..workflow`) reintroduced a circular import, because `application.workflow._models` imports `application.review` from inside its own module body. Reverted those two files' `WorkflowEvent` / `WorkflowState` / `utc_now` imports to their original direct-submodule form and reverted the mirroring facade rewrite the codemod applied to `application/workflow/_models.py`'s `InvoiceReviewRecord` / `LedgerReviewRecord` import, each with an explicit `CYCLE-BREAK-RATIONALE-WORKFLOW-REVIEW` comment documenting the exception (per the ADR's Ruling 2 cycle/cost carve-out).
- Verified `import aeat.application.workflow` and `import aeat.application.review` both succeed standalone after the fix.
- Normalised the rewritten import blocks with `ruff check --fix --select I` and `ruff format`.
- Verified `pytest --collect-only -q src/aeat` collected cleanly (0 import errors attributable to this batch).
- Committed the 29 files as one atomic explicit-pathspec commit.

## Outcome

29 files rewritten and committed (commit `3c1748da7`, `refactor(auth,filing,overview,wizard,review,workflow): route cross-package imports through owning facade (import-centralization W02)`). Behavior-preserving apart from the three documented cycle-break exceptions.

## Notes

Steps across `W02.P45`-`W02.P48`, `W02.P51`, and `W02.P52` are covered by this one record and this one commit, batched per the Wave dispatch brief. Five import statements across `application/review/_actions.py`, `application/review/_models.py`, and `application/workflow/_models.py` remain on their direct-submodule form (not the facade) as a documented, deliberate exception — the import-hygiene scanner will continue to flag these 5 sites until Wave W04 seeds them into the CI gate's allowlist. This was a real regression caught and fixed before commit, not a residual defect. Plan checkboxes for the covered Steps are left unchecked pending a follow-up bulk `vault plan step check` pass; the commit SHA above is the durable evidence trail.
