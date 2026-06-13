---
tags:
  - '#exec'
  - '#modelo-addressing-ux'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S119'
related:
  - '[[2026-06-04-modelo-addressing-ux-plan]]'
---

# `W05.P17.S119` Exact raw-ID leakage audit

Scope:
- `rg raw-id leakage audit`

## Description

- Run exact `rg` search for copied work-unit and calculation-revision ID language across source, locales, and docs.
- Separate internal/test identifier usage from operator-facing workflow guidance.
- Re-audit generated CLI reference output after command and documentation updates.
- Classify remaining narrative-doc and locale hits as advanced exact-addressing guidance or unrelated wording.

## Outcome

Exact raw-ID strings remain present, but the current hits do not show the common lifecycle path requiring operators to carry raw work-unit or calculation-revision IDs between commands.

Current narrative-doc hits are advanced exact-addressing guidance or unrelated to modelo work IDs:

- `docs/tutorials/index.md` says the lifecycle completed without copying raw internal IDs and notes that printed IDs remain for audit/replay/advanced exact addressing.
- `docs/getting-started.md`, `docs/how-to/quickstart.md`, `docs/how-to/reconcile.md`, and `docs/how-to/filing-spine.md` reserve exact work-unit or calculation-revision IDs for advanced options.
- `docs/how-to/import-bank-statements.md` says to copy a transaction id; that is a ledger transaction workflow, not modelo work-unit or calculation-revision addressing.

Current generated CLI reference hits are exact-addressing parameter entries:

- `docs/cli/app.rst` still documents optional or advanced `work_unit_id` and `calculation_revision_id` arguments for commands that retain exact-addressing compatibility.

Current locale hits are low-level error, validation, and exact-ID help strings:

- `src/aeat/locales/en.yml`
- `src/aeat/locales/es.yml`
- `src/aeat/locales/ca.yml`
- `src/aeat/locales/hu.yml`

Current source/test hits are internal identifier fields, assertions, or compatibility tests where content-addressed IDs remain authoritative.

## Notes

- Exact audit command: `rg -n "copy/paste|copy and paste|Copy the|copy the|paste the|<work-unit-id>|<calculation-revision-id>|work_unit_id|calculation_revision_id|work-unit ID|calculation revision ID|work unit ID|calculation-revision ID|[0-9a-f]{64}" docs src/aeat/locales src/aeat/entrypoints/cli src/aeat/application/modelo -g "*.md" -g "*.rst" -g "*.yml" -g "*.py"`.
- The remaining hits require semantic classification rather than blanket deletion because exact IDs are still part of the accepted internal audit and advanced operator contract.
