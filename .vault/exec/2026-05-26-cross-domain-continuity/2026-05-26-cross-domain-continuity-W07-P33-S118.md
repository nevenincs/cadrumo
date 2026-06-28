---
step_id: S118
tags:
  - "#exec"
  - "#cross-domain-continuity"
date: 2026-05-27
modified: '2026-05-27'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
  - "[[2026-05-26-cross-domain-continuity-W07-P33-S119]]"
---

# cross-domain-continuity W07.P33.S118 — `aeat app modelo compare` implementation

## Outcome

`aeat app modelo compare` verb implemented and committed at
`src/aeat/entrypoints/cli/_modelo.py`.

Commits: `604bf217d` (core implementation), `f4108869d` (period derivation fix)

## What was done

Added `modelo_compare` as `@app.command("compare")` (243 lines + 22 fix lines).

The verb:

1. Validates exactly two `--year` values are supplied.
2. For each year, calls `_best_revision(filing_year)` which:
   - Finds all work units for the modelo + year.
   - Prefers the most recent `VERIFICADO_COMPLETO` revision.
   - Falls back to the most recent `BORRADOR` with `is_draft_fallback=True`.
   - Returns `(revision, is_draft, period)` where period is from the owning
     work unit (not hardcoded to `"0A"` — fixes quarterly modelo compatibility).
3. Loads casilla metadata (label, section) from the snapshot for both years,
   preferring year_b definitions.
4. Iterates the union of both revisions' `casilla_values`, computes
   `delta = val_b - val_a` and `pct_change` (None when val_a = 0).
5. Groups rows by section and emits JSON + tab-delimited lines via `_emit()`.

Key design decision: period derived from the work unit owning the best revision,
not hardcoded. This ensures M130 quarterly work units (period=1T/2T/3T/4T) can
be compared without a `RegistrySnapshotError`.

## Files changed

- `src/aeat/entrypoints/cli/_modelo.py` (+243 lines initial, +22 lines fix)
