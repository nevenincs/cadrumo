---
tags:
  - "#exec"
  - "#fresh-cli-persona-repair"
date: '2026-05-27'
modified: '2026-05-27'
step_id: S171
commit: a0d7daa27
related:
  - "[[2026-05-21-fresh-cli-persona-repair-plan]]"
  - "[[2026-05-21-cli-persona-testimonials-plan]]"
---

# fresh-cli-persona-repair S171 — --revision/year temporal validation

## What was done

Extended `_validate_registry_target` in
`src/aeat/entrypoints/cli/_modelo.py` to refuse a `work create` call
when the supplied `--revision` does not cover the `--year`.  The new
`_revision_covers_year` helper checks `period_selector.years` (exact
list) and `year_from`/`year_to` (range) on the `ModeloRevision`.  When
coverage fails, `typer.BadParameter` is raised with a locale-translated
message naming the revision, the modelo, the filing year, and the set of
applicable revisions for that year.

Locale keys `revision_year_mismatch` and `revision_year_mismatch_no_match`
added to es/en/ca/hu.  Catalan is a first-class translation; hu uses
pass-through refs per convention.

Regression test added to
`src/aeat/entrypoints/cli/test_modelo_work_ux.py`:
`test_work_create_rejects_revision_that_does_not_cover_filing_year`
drives M131 `--revision 2026 --year 2024` and asserts non-zero exit,
no traceback, and both year values in diagnostic output.  Test passes
in 19 s against the real isolated backend.

## Files changed

- `src/aeat/entrypoints/cli/_modelo.py` — `_revision_covers_year` helper; `_validate_registry_target` signature extended to `(modelo, revision_id, year)`; call site updated
- `src/aeat/locales/es.yml` — `revision_year_mismatch` + `revision_year_mismatch_no_match`
- `src/aeat/locales/en.yml` — same keys in English
- `src/aeat/locales/ca.yml` — same keys in Catalan
- `src/aeat/locales/hu.yml` — pass-through refs
- `src/aeat/entrypoints/cli/test_modelo_work_ux.py` — regression test

## Verification

- `uv run pytest ...::test_work_create_rejects_revision_that_does_not_cover_filing_year` — PASSED
- `uv run python -m aeat.locales audit` — ca/en/es/hu all `ok`
