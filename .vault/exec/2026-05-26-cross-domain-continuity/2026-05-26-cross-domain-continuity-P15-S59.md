---
tags:
  - "#exec"
  - "#cross-domain-continuity"
date: 2026-05-27
modified: '2026-05-27'
step_id: S59
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# cross-domain-continuity P15.S59

## Outcome

Added `_casilla_revision_for_work_unit` and `_normalise_casilla_key` to
`src/aeat/entrypoints/cli/_modelo.py`.

The normaliser resolves bare integer tokens (e.g. `"69"`) to the canonical
casilla id (e.g. `"iva.resultado"`) by stripping leading zeros on both sides
for numeric equality. Handles multi-segment modelos where the same number
appears under multiple PREFIX segmentos by raising `typer.BadParameter` with
all candidates listed.

The `work_calculate` callback loads the active revision and runs the normaliser
over `casilla_pairs` only when `--casilla` flags were supplied.
`WorkUnitNotFoundError` is caught and converted to `BadParameter` before the
normalisation loop so the error message stays clean.

## Commit

`c73d60493` — W03.P15.S59+S60: bare-numeric --casilla normalisation + improved unknown-casilla error
