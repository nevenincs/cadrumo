---
tags:
  - '#exec'
  - '#import-centralization'
date: '2026-07-01'
modified: '2026-07-17'
step_id: 'S03'
related:
  - "[[2026-07-01-import-centralization-plan]]"
---

# Promote `Modelo`, `OUT_OF_SCOPE_OBLIGATIONS`, `Period`, `PeriodError`, `PostFilingEventKind`, `ResultDisposition`, `STRICT_FROZEN_CONFIG`, `TaxDomain`, `UNMODELED_OBLIGATIONS`, `classify_post_filing_event_kind`, `post_filing_event_is_actionable`, `resolve_active_bucket_id`, `result_disposition_is_refund` to `aeat.core.__all__` with eager re-exports so the 35 existing cross-package consumer site(s) can import from the facade

## Scope

- `src/aeat/core/__init__.py`

## Description

- Ran `dev/import_hygiene_scan.py` and read the fix-classification pairs for
  `aeat.core`; cross-checked each named symbol against `src/aeat/core/__init__.py`
  by direct grep and by importing the live package.
- Discovered that 11 of the 13 named symbols (`Modelo`, `Period`, `PeriodError`,
  `PostFilingEventKind`, `ResultDisposition`, `STRICT_FROZEN_CONFIG`, `TaxDomain`,
  `classify_post_filing_event_kind`, `post_filing_event_is_actionable`,
  `resolve_active_bucket_id`, `result_disposition_is_refund`) were already present
  in `__all__` and resolvable from the live package; the scanner's
  `discover_facades` only matches plain `ast.Assign` `__all__ = [...]` literals and
  misses `aeat/core/__init__.py`'s annotated `__all__: list[str] = [...]` form, so
  it never registers `aeat.core` as a real facade at all and reports every
  cross-package symbol reaching it as needing promotion.
- Promoted the two genuinely-missing symbols, `OUT_OF_SCOPE_OBLIGATIONS` and
  `UNMODELED_OBLIGATIONS`, from `._modelo` into `aeat.core.__all__` with eager
  re-exports (both are cheap dict literals, consistent with the rest of the
  eager surface).
- Extended the module docstring to name the two new exports.
- Ran `ruff check --fix` and `ruff format --diff` (clean), `pytest --collect-only -q
  src/aeat` (clean), `pytest -q src/aeat/core/tests` (passed), and the two
  pre-existing architecture-boundary gates (passed).

## Outcome

- `src/aeat/core/__init__.py` now exports `OUT_OF_SCOPE_OBLIGATIONS` and
  `UNMODELED_OBLIGATIONS`; every symbol named by this Step is confirmed
  resolvable from `aeat.core` (verified by direct import, not by re-running the
  scanner, since the scanner under-reports this package).
- Committed as `4e4bc3c26`.

## Notes

- Flagged for coordinator review: `dev/import_hygiene_scan.py`'s
  `discover_facades()` only detects `ast.Assign` `__all__` literals, not the
  annotated-assignment form (`__all__: list[str] = [...]`) that
  `src/aeat/core/__init__.py` uses. This makes `aeat.core` invisible to the
  `facades` dict entirely, so every cross-package reach into `aeat.core` is
  misclassified as "needs facade promotion" even when the symbol is already
  exported, and the package is absent from the JSON `facades` inventory. This is
  a scanner defect that should be fixed before the Ruling-8 CI gate is wired
  (Wave W04), since it inflates the `aeat.core` precondition count and would
  make the ratcheting baseline wrong for the highest-fanout owning package.
  Out of scope for this Step (facade promotion only); no scanner file was
  touched.
