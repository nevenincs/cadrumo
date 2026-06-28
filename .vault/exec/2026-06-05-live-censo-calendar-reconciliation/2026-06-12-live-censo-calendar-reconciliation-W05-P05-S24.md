---
tags:
  - '#exec'
  - '#live-censo-calendar-reconciliation'
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S24'
related:
  - '[[2026-06-05-live-censo-calendar-reconciliation-plan]]'
---

# W05.P05.S24 - pull-only live filed and expedientes re-verification

## Description

- Re-verify the live filed and expedientes bulk-read command surfaces after backend and typed `Period` drift.
- Confirm bulk authenticated reads are exposed through `pull` options rather than a registered `pull-all` command.
- Track the user-requested CLI verb drift check in the current live-censo calendar plan.

## Outcome

The registry CLI gate confirms live filed and expedientes still register `pull` and do not register `pull-all`. Live authenticated smoke used only `pull`:

- `app live filed pull --from-year 2026 --to-year 2026`
- `app live expedientes pull --from-year 2026 --to-year 2026`

Both commands emitted the expected `app.live.*.pull` envelope command and `mode = bulk`.

## Verification

- `vaultspec-rag search --timeout 300 "CLI verb drift pull pull-all live AEAT filing history messages calendar modelos"` returned the prior CLI pull/file ADR, plan, and S14/S15 live-censo execution records.
- `uv run pytest src/aeat/entrypoints/cli/tests/test_registry_cli.py -m integration -q` passed with 54 tests before the final combined gate.
- `uv run pytest src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py src/aeat/entrypoints/cli/tests/test_registry_cli.py -m integration -q` passed with 63 tests.
- `uv run ruff check src/aeat/application/live/_justificante.py src/aeat/application/live/tests/test_justificante_reconcile_from_persisted.py src/aeat/application/calculations/_cross_period_clean_state.py src/aeat/application/calculations/tests/test_cross_period_clean_state.py src/aeat/application/overview/_calendar.py src/aeat/application/overview/tests/test_calendar.py src/aeat/entrypoints/cli/_overview.py src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py src/aeat/entrypoints/cli/tests/test_registry_cli.py` passed.
- `vaultspec-code-reviewer` reviewed S23/S24 and reported no findings.

## Live Verification

Fresh isolated live profile `live-user-smoke-20260612-s23` was created under `var/live-user-smoke/20260612-s23` using file-backed storage and a process-local development passphrase. `config profile status` and `app overview calendar --from 2026-01-01 --to 2026-12-31 --allow-incomplete` succeeded; the calendar derived Modelo 100, 303, 390, and 721 obligations with separate local readiness, AEAT submission, and justificante verification state.

`config profile censo pull` reached AEAT and refused closed because G313 returned no readable censo for the profile identity. `app live filed pull --from-year 2026 --to-year 2026` succeeded with `captured_count = 0`, `failed_count = 8`, and no justificante artefacts. `app live expedientes pull --from-year 2026 --to-year 2026` succeeded with one persisted snapshot and no declarations. `app live notifications pull` persisted one AEAT notification snapshot, and the subsequent overview calendar projected it as a message event dated 2026-06-03. `app live justificante pull --modelo 303 --year 2026 --period 1T` refused because no filed declaration exists for that period, so justificante verification remained false.
