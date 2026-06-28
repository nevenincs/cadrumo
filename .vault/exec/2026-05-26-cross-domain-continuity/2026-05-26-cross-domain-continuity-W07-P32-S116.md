---
step_id: S116
tags:
  - "#exec"
  - "#cross-domain-continuity"
date: 2026-05-27
modified: '2026-05-27'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
  - "[[2026-05-26-cross-domain-continuity-W07-P32-S117]]"
---

# cross-domain-continuity W07.P32.S116 — `aeat app modelo project` implementation

## Outcome

`aeat app modelo project` verb implemented and committed at
`src/aeat/entrypoints/cli/_modelo.py`.

Commit: `1f553d99c`

## What was done

Added `modelo_project` as a top-level `@app.command("project")` handler (258
lines) before `__all__ = ["app"]`.  The verb:

1. Guards with `_require_active_profile()`.
2. Retrieves all M130 work units for `--year` via `list_work_units()`, filters
   to BORRADOR state and quarterly periods (1T-4T).
3. Loads the latest `CalculationRevision` per quarter via
   `list_calculation_revisions()`.
4. Aggregates casilla 03 (rendimiento neto) and casilla 19 (resultado final /
   pagos fraccionados) across all available quarters.
5. Extrapolates to full year when fewer than 4 quarters are present
   (factor = 4 / quarters_filed, rounding to 0.01).
6. Builds M100 snapshot inputs (`0505` = projected rendimiento neto,
   `0604` = total pagos fraccionados) and default bindings (estimacion-directa
   flag, retenciones zeroed out, CCAA enum binding).
7. Runs `calculate_registry_snapshot` with `date_context = {filing_period:
   date(year, 12, 31)}`.
8. Emits JSON payload and tab-delimited lines with `_emit()`.

Supports `--casilla KEY=VALUE` and `--binding KEY=VALUE` overrides for
supplement inputs (e.g. `--casilla 0513=1150` for LIRPF Art. 57.2 age
supplement).

## Files changed

- `src/aeat/entrypoints/cli/_modelo.py` (+258 lines)
