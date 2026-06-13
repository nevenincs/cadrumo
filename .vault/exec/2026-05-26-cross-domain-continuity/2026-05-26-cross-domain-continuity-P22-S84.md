---
tags:
  - "#exec"
  - "#cross-domain-continuity"
date: 2026-05-27
modified: '2026-05-27'
step_id: S84
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# cross-domain-continuity P22.S84

## Outcome

Updated casilla 01 in `src/aeat/_data/registry/aeat/modelos/130/revisions/2019-y-siguientes/casillas/0001-casillas.toml`:

- `input_kind` changed from `"manual"` to `"bound"`
- `binding = "modelo-130-actividad-economica-ingresos-cumulative"` added

This wires the Ingresos casilla to the new income aggregation resolver. Registry
validation confirms `casilla_aggregation.casilla_values["01"]` is now populated by
the ledger pipeline rather than manual entry. All other casilla fields are unchanged.

## Commit

`3fe34b561` — S83+S84: register M130 income binding + wire casilla 01 to ledger aggregation
