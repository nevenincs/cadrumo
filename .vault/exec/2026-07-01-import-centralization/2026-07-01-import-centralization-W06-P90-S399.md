---
tags:
  - '#exec'
  - '#import-centralization'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S399'
related:
  - "[[2026-07-01-import-centralization-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace import-centralization with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S399 and 2026-07-01-import-centralization-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Re-run dev/import_hygiene_scan.py and confirm zero production Family-1 cross-package private-import violations, then flip the Wave W04 ratchet gate to hard-zero mode and ## Scope

- `dev/import_hygiene_scan.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Re-run dev/import_hygiene_scan.py and confirm zero production Family-1 cross-package private-import violations, then flip the Wave W04 ratchet gate to hard-zero mode

## Scope

- `dev/import_hygiene_scan.py`

## Description

- Re-ran the scanner and confirmed exactly 5 production Family-1 cross-package private-import sites remain, all in `application/review/_actions.py`, `application/review/_models.py`, and `application/workflow/_models.py`.
- Investigated each site individually for TYPE_CHECKING-plus-facade deferral: walked the AST of each importer to enumerate every `Load`-context occurrence of the imported names.
- Confirmed `WorkflowEvent` is directly instantiated at runtime in `_actions.py` (`WorkflowEvent(action=action, reason=reason)`) and used as a pydantic `BaseModel` field type (`tuple[WorkflowEvent, ...]`) on `LedgerReviewRecord`/`InvoiceReviewRecord` in `_models.py`; pydantic v2 resolves field-type annotations eagerly at class-definition time even under `from __future__ import annotations`, so this is not deferrable.
- Confirmed `utc_now` is called directly and passed as a live `Field(default_factory=utc_now)` callable in both `review` files; not an annotation, not deferrable.
- Confirmed `InvoiceReviewRecord`/`LedgerReviewRecord` are pydantic field types on `WorkflowState` in `workflow/_models.py`; the module already carries a TYPE_CHECKING-only facade import of the same two names for static analysis, and the runtime private-submodule import is the one that resolves the names for the explicit `WorkflowState.model_rebuild()` call immediately following it.
- Made no source-code edits, since restructuring the review/workflow module boundary to remove the genuine cycle was explicitly out of scope for this pass.
- Enriched the `reason` field for all 5 sites in the checked-in ratchet baseline with the AST usage evidence above, so the runtime-bound disposition is auditable without re-deriving it.
- Verified the scoped test surfaces (`application/review`, `application/workflow`, excluding one file broken by unrelated concurrent peer WIP in `domain.modelos`) collect and pass: 185 passed, 3 unrelated failures traced to the peer's in-flight `domain.modelos` refactor.
- Ran the import-hygiene gate; the two Family-1 assertions fail only on 2 sites in `adapters/persistence/profile/modelos_work_units.py`, which is the same concurrent peer WIP, not a site owned by this Step.

## Outcome

Production Family-1 cross-package private-import count could not be reduced by this pass: all 5 residual sites are genuinely runtime-bound (pydantic field-type resolution, direct instantiation, or a `default_factory` callable reference), not annotation-only usages amenable to a `TYPE_CHECKING` deferral. The Wave W04 ratchet gate was NOT flipped to hard-zero, because doing so would require either (a) restructuring the `review`/`workflow` module boundary to break the genuine cycle, which is out of scope for a mechanical import-mechanism pass, or (b) accepting the current baseline as a permanent, named exception. This Step's `hard-zero` acceptance criterion is not met and the checkbox remains unchecked pending a future structural decomposition decision.

## Notes

No regressions introduced; zero production source files touched. The 2 currently-failing import-hygiene gate assertions and the 3 currently-failing `workflow` tests are all attributable to a concurrent peer's uncommitted `domain.modelos` refactor (removal of `WorkUnitCatalogueRepository`/`WorkUnitPersistenceError` from that package's facade), verified via `git diff --stat` against the affected files before and confirmed unrelated to this Step's scope. That WIP was left untouched per the standing git-worktree-safety and swarm-orchestration disciplines.
