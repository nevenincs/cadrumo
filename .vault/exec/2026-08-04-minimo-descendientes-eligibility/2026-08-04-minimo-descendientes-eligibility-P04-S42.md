---
tags:
  - '#exec'
  - '#minimo-descendientes-eligibility'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:046ba8ee639c8470264c4e5c2f622a390b595e7ef15cf4702f0e97f11d5d3d89'
step_id: 'S42'
related:
  - "[[2026-08-04-minimo-descendientes-eligibility-plan]]"
---
# Add guided pages for descendant completion month and death date

## Scope

- `src/cadrumo/application/wizard/_descendant_group.py`
- `src/cadrumo/application/wizard/_persistence.py`
- `src/cadrumo/application/wizard/tests/test_descendant_group.py`
- `src/cadrumo/application/wizard/tests/test_descendant_persistence.py`
- `src/cadrumo/locales/`
- `2026-08-04-minimo-descendientes-eligibility-P04-S39`

## Description

- Add optional guided pages for the descendant's death date and the month in which the mother completed the post-birth contribution requirement.
- Bound the completion month to calendar months and expose translated prompts, help, and refusal copy in all four shipped locales.
- Project both answers into the canonical descendant record and re-project them when a persisted setup flow resumes.
- Correct the S39 execution record so its entry-surface claim names the flag door it actually delivered.
- Exercise the production flow engine and encrypted profile store without fakes, mocks, stubs, patches, skips, or mirrored business logic.

## Outcome

The guided setup walk can now collect both facts that previously existed only in the `--descendiente` flag grammar. The answers persist to the canonical `fallecimiento` and `alta_posterior_nacimiento_mes` fact paths and survive save, reload, and resume seeding.

The completion month refuses values outside 1 through 12 before persistence. Every new copy key resolves in Spanish, English, Catalan, and Hungarian.

## Verification

`uv run --no-sync ruff check src/cadrumo/application/wizard/_descendant_group.py src/cadrumo/application/wizard/_persistence.py src/cadrumo/application/wizard/tests/test_descendant_group.py src/cadrumo/application/wizard/tests/test_descendant_persistence.py`

`All checks passed!`

`uv run --no-sync basedpyright src/cadrumo/application/wizard/_descendant_group.py src/cadrumo/application/wizard/_persistence.py src/cadrumo/application/wizard/tests/test_descendant_group.py src/cadrumo/application/wizard/tests/test_descendant_persistence.py`

`0 errors, 0 warnings, 0 notes`

`uv run --no-sync pytest -n 0 -q src/cadrumo/application/wizard/tests/test_descendant_group.py src/cadrumo/application/wizard/tests/test_descendant_persistence.py src/cadrumo/application/wizard/tests/test_wizard_translations_resolve.py`

`32 passed in 8.65s`

## Notes

The shared Git index remained locked by another process throughout this Step, so the payload is intentionally unstaged and uncommitted. Unrelated locale edits already present in the shared worktree were preserved; the S42 leaves were added through the locale CLI.
