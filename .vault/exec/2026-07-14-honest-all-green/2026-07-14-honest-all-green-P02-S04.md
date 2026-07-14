---
tags:
  - '#exec'
  - '#honest-all-green'
date: '2026-07-14'
modified: '2026-07-14'
step_id: 'S04'
related:
  - "[[2026-07-14-honest-all-green-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace honest-all-green with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S04 and 2026-07-14-honest-all-green-plan placeholders are machine-filled by
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
     The Register or rehome the FormerProduct exception classes so the exception-base-hygiene gate passes without allowlist mutes and ## Scope

- `src/cadrumo/core/errors` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Register or rehome the FormerProduct exception classes so the exception-base-hygiene gate passes without allowlist mutes

## Scope

- `src/cadrumo/core/errors`

## Description

- Confirmed no peer WIP in `src/cadrumo/core/errors` before editing.
- Ran `test_exception_base_hygiene.py` and enumerated the exact 3
  violations: `FormerProductStateError(RuntimeError)`,
  `FormerProductAuthSessionStateError(RuntimeError)`, and
  `Modelo210AgrupacionRentaRowsError(ValueError)`.
- Read each class's definition and every call site to determine root
  cause rather than muting the gate:
  - `FormerProductStateError` is raised from inside `Settings`/pydantic
    validation during bootstrap (`_resolve_database_url_for_active_profile`
    -> `refuse_former_product_database`), before the `AeatError` registry
    can be relied upon. The CLI boundary (`entrypoints/cli/_errors.py`)
    explicitly catches it ahead of the broad `AeatError` arm and
    translates it into a registered `CliRefusedBoundaryError` — the same
    shape as the existing allowlisted harness-boundary precedents
    (`SchemaResolutionError`, `LiveHarnessError`).
  - `FormerProductAuthSessionStateError` is the identical former-product
    refusal shape, raised at the session-store storage boundary
    (`_repository_for_path`) before any repository/registry access; a
    refusal-only signal that never reads, moves, or adopts the retired
    state it detects.
  - `Modelo210AgrupacionRentaRowsError` is a private domain
    row-validation carrier (`domain/modelos/_row_models.py`) with
    exactly one production call site
    (`application/modelo/_m210_agrupacion_renta.py`), which always
    converts it to the `AeatError`-derived `ModeloError` before it
    leaves the module boundary — the same shape as the existing
    `_RowParseError`/`_WizardFieldError` private-carrier precedents.
- Registered all three in `_ALLOWLIST` with the above rationale (no
  gate weakening; every entry documents why the class is a legitimate
  root, not why the check should be skipped).
- Re-ran the gate: both tests green
  (`CADRUMO_LOCAL_STORAGE_ROOT` pointed at a scratch directory for the
  duration of the run, working around an unrelated real leftover
  `aeat.db` file on this dev machine's storage root that otherwise
  trips `FormerProductStateError` during eager `Settings()`
  construction — never touching the real file).
- Ran ruff check + format on the touched test file; both clean.

## Outcome

Landed in commit `7fa034c84c`. `test_exception_base_hygiene.py` passes
both `test_production_exception_classes_do_not_introduce_unregistered_builtin_roots`
and `test_exception_base_hygiene_allowlist_carries_review_rationales`.
No production behavior change; the gate is genuinely green at HEAD via
root-cause classification of each root, not an allowlist mute of an
unexamined violation.

## Notes

No incidents. Blocked briefly on exec-record scaffolding because the
feature had no ADR document yet (`vault add exec` requires
research -> ADR -> plan -> exec); flagged to the team lead rather than
authoring the decision record myself, and the ADR landed shortly after
from elsewhere in the swarm.
