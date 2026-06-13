---
step_id: S109
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
  - '[[2026-05-27-centralized-module-drift-audit]]'
---

# codebase-solidification W01.P03.S109 — DT12/SAL computation error sites localized

## Outcome

Replaced two `raise typer.BadParameter(str(exc))` bare sites in `_modelo.py`:

- Line 3018 (DT12 computation): now uses
  `tr("cli.app.modelo.work.dt12_computation_error", message=str(exc))`
- Line 3056 (SAL computation): now uses
  `tr("cli.app.modelo.work.sal_computation_error", message=str(exc))`

Added locale keys `cli.app.modelo.work.dt12_computation_error` and
`cli.app.modelo.work.sal_computation_error` (both with `%{message}` slot) to
all four locales (en, es, ca, hu) via `python -m aeat.locales set`.

## Files touched

- `src/aeat/entrypoints/cli/_modelo.py`
- `src/aeat/locales/en.yml`
- `src/aeat/locales/es.yml`
- `src/aeat/locales/ca.yml`
- `src/aeat/locales/hu.yml`

## Verification

`uv run --no-sync python -m aeat.locales audit` → all four locales ok.
