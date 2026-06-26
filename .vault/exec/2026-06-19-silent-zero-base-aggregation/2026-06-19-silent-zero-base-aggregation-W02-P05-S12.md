---
tags:
  - '#exec'
  - '#silent-zero-base-aggregation'
date: '2026-06-20'
modified: '2026-06-20'
step_id: 'S12'
related:
  - "[[2026-06-19-silent-zero-base-aggregation-plan]]"
---




# bind M100 casilla 0171 to the annual income aggregation (project verb uses the formula-runtime path, so no disentanglement needed) with grounded legal_refs (LIRPF art. 27/28)

## Scope

- `src/aeat/_data/registry/aeat/modelos/100/`
- `src/aeat/_data/registry/aeat/modelos/100/`

## Description

Bound Modelo 100 casilla 0171 "Ingresos de explotación" to the annual income
aggregation, closing its silent zero for direct M100 filings.

- Casilla 0171 set to `input_kind = bound`, `binding = renta-2025-ledger-income-0171`.
- New binding TOML `renta-2025-ledger-income-0171` (source
  `ledger_renta_income_aggregation`, selector modelo=100 target_casilla=0171 fact
  ingresos_integros_sum), grounded in LIRPF art. 27/28 with a source citation.
- Added the binding to the economic-activities construct's binding list.

Files under
`src/aeat/_data/registry/aeat/modelos/100/revisions/2025/` (casillas, bindings,
constructs).

## Outcome

Registry loads; 0171 resolves from the ledger annual income aggregation. No
disentanglement of the project verb was required (it calculates via the
formula-runtime path).

## Notes

None.
