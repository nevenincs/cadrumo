---
tags:
  - '#exec'
  - '#import-centralization'
date: '2026-07-02'
modified: '2026-07-17'
step_id: 'S399'
related:
  - "[[2026-07-01-import-centralization-plan]]"
---

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

### Follow-up structural pass (2026-07-03)

A separate follow-up pass performed option (a): extracted the 4 mutually-needed
runtime-bound names (`WorkflowEvent`, `utc_now`, `InvoiceReviewRecord`,
`LedgerReviewRecord`) into a new dependency-free shared leaf module,
`aeat.application._workflow_review_models`, that neither `application.review`
nor `application.workflow` depends on. Both packages now import these names
from the shared module instead of from each other's private submodule; every
consumer outside these two packages is unaffected because it already imported
through the public `application.review` / `application.workflow` facades,
which keep re-exporting the same names. Full rationale, considered options, and
consequences are recorded in a dedicated ADR
(`2026-07-03-review-workflow-cycle-break-adr`) rather than repeated here.

Verified: `import aeat.application.review` and `import aeat.application.workflow`
each succeed cleanly and independently in either order (no partial-init
re-entry); `pytest --collect-only -q src/aeat/application/review
src/aeat/application/workflow` collects 208 tests cleanly; the full scoped
suite for both packages passes 208/208, and `application/invoices`,
`application/auth`, `application/user_profile` (the three packages that consume
`WorkflowEvent`/`WorkflowState`/`InvoiceReviewRecord` via the public facades)
pass 315/315. `dev/import_hygiene_scan.py` now reports zero production
Family-1 sites for the `application.review` <-> `application.workflow` pair
(the Family-3 duplicate-symbol entries for `WorkflowEvent`, `WorkflowState`,
`InvoiceReviewRecord`, `LedgerReviewRecord` are also gone). The checked-in
`dev/import_hygiene_baseline.json` `sites` list for this exception is now
permanently `[]`, and `src/aeat/tests/test_import_hygiene_gate.py`'s two
production Family-1 assertions were updated to hard-zero shape (ratchet against
an empty baseline; any new site is a straight, named failure) rather than the
prior 5-site ratchet ceiling.

This Step's acceptance criterion is satisfied FOR THE `application.review` /
`application.workflow` PAIR THIS STEP WAS WRITTEN TO TRACK, but NOT for the
scanner's full production Family-1 surface: a separate, pre-existing and
unrelated production Family-1 regression (10 sites,
`adapters.persistence.profile.modelos_*` importing `domain.modelos` private
submodules) was discovered as a side effect of re-running the scanner during
this pass. It predates this work — 2 sites are already committed on this branch
(`05ab9eb2b2`), 1 file is still in-flight, uncommitted peer work under the
concurrent `arch-remediation-ports-inversion` campaign — and is explicitly out
of this Step's original scope (it names `dev/import_hygiene_scan.py` /
`application.review` / `application.workflow`, not `domain.modelos`). Per
`full-tree-gate-must-distinguish-owner`, this Step's checkbox remains
UNCHECKED: the review/workflow cycle-break is structurally closed, but the
Step's literal "confirm zero production Family-1... violations" criterion
(read as the whole scanner) is not met while the unrelated `domain.modelos`
regression stands. That regression is left for the
`arch-remediation-ports-inversion` campaign's own closeout to register or fix.

## Notes

No regressions introduced; zero production source files touched. The 2 currently-failing import-hygiene gate assertions and the 3 currently-failing `workflow` tests are all attributable to a concurrent peer's uncommitted `domain.modelos` refactor (removal of `WorkUnitCatalogueRepository`/`WorkUnitPersistenceError` from that package's facade), verified via `git diff --stat` against the affected files before and confirmed unrelated to this Step's scope. That WIP was left untouched per the standing git-worktree-safety and swarm-orchestration disciplines.

The 2026-07-03 follow-up pass touched: `src/aeat/application/_workflow_review_models.py` (new), `src/aeat/application/review/_models.py`, `src/aeat/application/review/_actions.py`, `src/aeat/application/workflow/_models.py`, `dev/import_hygiene_baseline.json`, `src/aeat/tests/test_import_hygiene_gate.py`. It made zero edits to `domain.modelos` or `adapters.persistence.profile`, and zero edits to the plan document itself (the plan file is under active concurrent peer reconciliation per prior git-incident history recorded in the campaign's closeout audit; this pass deliberately avoided mutating it and instead amended this existing Step Record's body prose in place, per the allowed-manual-edits convention for CLI-scaffolded vault documents).

### Closeout verification (2026-07-04)

The unrelated `domain.modelos` / `adapters.persistence.profile.modelos_*` production Family-1 regression that blocked this Step's literal whole-scanner criterion at 2026-07-03 has since been resolved by the owning `arch-remediation-ports-inversion` campaign. Re-ran `dev/import_hygiene_scan.py` at HEAD: it reports zero distinct production files with a cross-package private import, zero production Family-1 sites, and zero Family-4 underscore-named `__all__` entries. Ran the ratchet gate `src/aeat/tests/test_import_hygiene_gate.py`: the three production Family-1 assertions (baseline-is-hard-zero, count-does-not-exceed, exactly-the-named-set) and the Family-4 hard-zero assertion all pass. The only remaining gate failures are in the SEPARATE test-only debt family (57 current vs 54 baselined — 5 new undocumented test-only reaches introduced by unrelated peer campaigns: corpus-search error registration, calc-sheets BOE consistency, config #591 certificate expiry, review #421 review-package build, and mcp evidence-scrubbing), which is governed independently of the production baseline and is peer-owned per `full-tree-gate-must-distinguish-owner`. This Step's acceptance criterion — zero production Family-1 violations, gate in hard-zero mode — is met at HEAD; the checkbox is closed here.
