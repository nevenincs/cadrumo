---
tags:
  - '#exec'
  - '#declaracion-extraction-architecture'
date: '2026-05-27'
modified: '2026-05-27'
step_id: 'S195'
related:
  - '[[2026-05-21-declaracion-extraction-architecture-plan]]'
---

# declaracion-extraction-architecture W08.P35.S195

Added two tests to `src/aeat/domain/calculations/registry/test_census_modelo_registry_data.py`:
- `test_m036_revision_periods_are_lowercase_canonical` — lint test loading M036 in isolation
- `test_m036_period_case_lint_detects_uppercase_drift` — anti-evasion proof test

Also imported `load_modelo_directory` from `._loader` to enable isolated M036 loading.

## Description

`_active_036_ownership_from_registry` compares `revision.period_selector.periods` against
`CENSUS_MODELO_EVENT_KINDS = ("alta", "modificacion", "baja")` with a case-sensitive equality
guard. The `_temporal.py` case-insensitive mask does not protect this path. AEAT Anexo 3 HTML
tables display ALTA/MODIFICACION/BAJA uppercase; a registry author mirroring that display
convention would silently break the ownership resolution (history: commit 33783e00c, reverted
472de9c02 within 21 minutes).

The lint test calls `load_modelo_directory` directly on the M036 directory to avoid triggering
unrelated registry failures in other modelo directories. It iterates all revisions, checking
both `period_selector.periods` and every `filing_schedule.periods` tuple with
`_assert_periods_lowercase`, which fails if any period value differs from its `.lower()` form.

The proof test confirms the assertion fires for all-uppercase `("ALTA", "MODIFICACION", "BAJA")`
and for mixed-case `("Alta", "modificacion", "Baja")`, proving the check is not tautological.

## Tests

Both new tests pass in isolation (`2 passed in 0.18s`). The three failures in the full file run
are pre-existing WIP from another agent: M100 TOML changes that add `ley-35-2006:art-84` and
`ley-35-2006:art-7-h` to the legal catalogue without the required corpus text grounding. Those
failures are unaffected by this step.
