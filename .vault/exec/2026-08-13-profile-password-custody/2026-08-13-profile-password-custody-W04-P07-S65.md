---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:be2b34c6a871a5773e592cbe188607d50ec967350331effd32e8aa2b3f6e05a6'
step_id: 'S65'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Sol Medium give the M303 per-activity prorrata completeness refusal one home, since the invariant is genuinely enforced on the live export path but raises an untranslated internal registry error, while an orphaned second implementation that can never fire carries the operator-facing typed refusal whose localisation key already ships in all four catalogues, so the better surface and the better position are currently in different objects and deleting either loses something real

## Scope

- `src/cadrumo/application/filing/ and src/cadrumo/domain/calculations/registry/_m303_prorrata_activity_projection.py`

## Description

- Confirmed which implementation fires: `project_m303_prorrata_activity_rows` in the
  registry package is the sole callable reached from `_project_prorrata_record` in
  `application/filing/_projection.py`, which `_export.py`'s `export_draft` invokes on
  every real fixed-width export; a targeted registry-side incompleteness case reproduced
  the raise. `assert_m303_prorrata_activity_rows_complete` in the deleted
  `application/filing/_m303_prorrata_activity_rows.py` had zero production callers, was
  not exported from `application/filing/__init__.py`'s facade, and had no dedicated unit
  test -- a full-repo grep found only its own module and the AST-sweep roster naming it.
- Added `RegistryValidationError.for_prorrata_activity_rows_incomplete(*, ejercicio)` to
  `domain/calculations/registry/_errors.py`, following the file's established
  `for_*` canonical-factory idiom. It reuses the pre-existing, already four-locale-shipped
  key `application.filing.m303_prorrata_activity_rows.errors.activity_rows_incomplete`
  as `translated_message`, with `context={modelo, filing_year, required_slot_first,
  required_slot_last}`.
- Rewired the live raise site in `_m303_prorrata_activity_projection.py` to call the new
  factory instead of constructing a bare, untranslated `RegistryValidationError`.
- Deleted `application/filing/_m303_prorrata_activity_rows.py` outright (no re-export, no
  delegating wrapper) and dropped `_m303_prorrata_activity_rows.py` from
  `_SWEPT_MODULES` in `test_filing_refusal_message_key_only.py`, the only surface still
  naming it.
- Added `test_incomplete_ejercicio_refuses_with_the_typed_localised_operator_facing_refusal`
  and `test_complete_ejercicio_is_not_refused_by_the_activity_rows_completeness_gate` to
  `domain/calculations/registry/tests/test_modelo_303_prorrata_activity_endpoints.py`,
  covering both directions of the guard and resolving the locale key live in all four
  catalogues via `core.i18n.tr(..., locale=...)`.

## Outcome

`RegistryValidationError` did not need to import `domain.filing.FilingExportError` to
gain the good surface: `RegistryValidationError` already inherits `CadrumoError` and
already supports `translated_message` + `context`, resolved through the same
`resolve_error_message` path any `CadrumoError` uses. That let the fix land entirely
inside the registry package the live raise already occupies, with no new cross-package
import and no cycle risk -- `domain.filing` already imports from
`domain.calculations.registry` (`_schema.py`), so the reverse import would have been a
cycle. Deleting either implementation outright would have lost something real: deleting
the registry-side function would have left the applicable-year completeness invariant
unenforced on the only path that ever runs it (a silent-under-declaration regression);
deleting the orphan's raise shape alone, without touching the live site, would have left
the live refusal permanently untranslated. The landed shape keeps the live position and
gains the typed, localised, operator-facing refusal at that same position.

Verification:
- `pytest domain/calculations/registry/tests/test_modelo_303_prorrata_activity_endpoints.py`
  targeted at the two new tests plus the pre-existing complete-case projection test --
  3 passed. The incomplete case (3 of 5 slots) raises with the exact `translated_message`
  and `context`, and resolves to a non-key-echoing, non-empty string in `en`, `es`, `ca`
  and `hu` via `tr(...)`. The complete case (5 of 5 slots) is not refused and yields all
  five projected rows -- confirms the guard is not refuse-everything-broken either.
- `pytest application/filing/tests/test_filing_refusal_message_key_only.py` -- full file,
  all green; the AST sweep's own roster-honesty tests confirm the swept/unswept module
  lists still name real files after the deletion.
- `pytest --collect-only src/cadrumo/application/filing src/cadrumo/domain/calculations/
  registry` -- 5194/5223 collected, 0 errors: no dangling import to the deleted module.
- `ruff check` and `basedpyright` on every touched file (both changed source modules and
  both changed test files) -- clean.
- The full `domain/calculations/registry/tests/test_modelo_303_prorrata_activity_endpoints.py`
  file and the full `application/filing` package were also run. Both show a large,
  pre-existing block of unrelated failures (14 of 17 in the registry endpoint file; 235
  failed / 11 errors across `application/filing`), every one of them tracing to
  `RegistryValidator.validate_modelo` / `_ValidatedRegistryAuthority.load` refusing the
  bundled modelo-186 layout source and several M303/M130 revisions for missing export
  layouts -- the in-flight registry authority-grade sweep (HEAD at execution time:
  `8a7ded927c registry: continue authority-grade sweep (round 42)`), confirmed
  pre-existing by `git status` showing no uncommitted registry-data changes and by these
  failures reproducing on tests (`test_schema_completeness.py`, `test_import.py`) that
  never touch prorrata code. None of these failures reference this Step's touched code
  or symbols. Re-read at report time; still the same state.

## Notes

No locale file was touched -- the reused key already carried real strings in all four
catalogues before this Step, confirmed by resolving (not grepping) each one.
