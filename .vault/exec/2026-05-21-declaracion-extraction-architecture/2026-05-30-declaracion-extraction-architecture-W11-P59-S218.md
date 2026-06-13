---
step_id: "W11.P59.S218"
tags:
  - "#exec"
  - "#declaracion-extraction-architecture"
date: 2026-05-30
modified: '2026-05-30'
related:
  - "[[2026-05-21-declaracion-extraction-architecture-plan]]"
  - "[[2026-05-21-declaracion-extraction-architecture-adr]]"
---

# declaracion-extraction-architecture W11.P59.S218

## Step

Audit M349 closure-formula feasibility against Orden HAC/174/2020 Anexo Diseño de Registro; establish EXTRACTION-ONLY-INTRINSIC domain verdict; update verification chain test docstring with AEAT-published arithmetic authority.

Scope: `src/aeat/adapters/inbound/declaracion/test_verification_chain.py`

## Findings

### UNIT 1 — M349 current state

The `2020-y-siguientes` revision has 4 casillas in `section = ["declarante", "resumen"]` (the Tipo 1 header record), all with `input_kind = "bound"`:

- `decl.numero-operadores` (pos. 138-146) — bound to `vat-349-declarante-numero-operadores` (count_distinct, exclude_rectifications)
- `decl.importe-operaciones` (pos. 147-161) — bound to `vat-349-declarante-importe-operaciones` (sum, exclude_rectifications)
- `decl.numero-rectificaciones` (pos. 162-170) — bound to `vat-349-declarante-numero-rectificaciones` (count_distinct, only_rectifications)
- `decl.importe-rectificaciones` (pos. 171-185) — bound to `vat-349-declarante-importe-rectificaciones` (sum, only_rectifications)

No formulas exist in the registry. The extraction profile `modelo-349-declaracion-pdf` targets these 4 casillas via `named_label` match strategy. The synthetic fixture `2024-1T.pdf` produces `numero-operadores=5`, `importe-operaciones=1234.56`, `numero-rectificaciones=0`, `importe-rectificaciones=0.00`. Completeness manifest lists all 4 casilla positions.

### UNIT 2 — AEAT authority for closure semantics

Orden HAC/174/2020 Anexo (Diseño de Registros Modelo 349, pp. 11-12) defines:

- **pos. 138-146 (NÚMERO TOTAL DE OPERADORES INTRACOMUNITARIOS):** "(Número de registros de operador intracomunitario (registro de tipo 2) con clave de operación, posición 133, igual a 'E', 'M', 'H', 'T', 'A', 'S', 'I', 'R', 'D' o 'C'."
- **pos. 147-161 (IMPORTE DE LAS OPERACIONES INTRACOMUNITARIAS):** "(Suma de Bases Imponibles e importes, posiciones 134-146, de los registros de operador intracomunitario (registro de tipo 2) y clave de operación, posición 133, igual a 'E', 'M', 'H', 'T', 'A', 'S', 'I', 'R', 'D' o 'C')."
- **pos. 162-170 (NÚMERO TOTAL DE OPERADORES INTRACOMUNITARIOS CON RECTIFICACIONES):** "(Número de registros de rectificaciones (registro de tipo 2) con clave de operación, posición 133, igual a 'E', 'M', 'H', 'T', 'A', 'S', 'I', 'R', 'D' o 'C'."
- **pos. 171-185 (IMPORTE DE LAS RECTIFICACIONES):** "(Suma de Bases Imponibles Rectificadas, posiciones 153-165, de los registros de rectificaciones (registro de tipo 2) y clave de operación, posición 133, igual a 'E', 'M', 'H', 'T', 'A', 'S', 'I', 'R', 'D' o 'C'."

### UNIT 3 — Verdict: Outcome (c) EXTRACTION-ONLY-INTRINSIC

The closure totals are defined as counts and sums over **Tipo 2 records** in the submitted fichero. This is row-array aggregation over the fichero record stream, not casilla-to-casilla arithmetic. The declaracion_pdf surface exposes only the Tipo 1 header record (the printed summary page); the Tipo 2 detail rows appear only in the telematic fichero format.

The formula DSL's `add`/`subtract`/`multiply` operators accept named single casillas as arguments. There is no `SUM-over-rows` construct. Authoring a formula `decl.importe-operaciones = sum(op.base-imponible[*])` would require a new row-array aggregation primitive in the DSL — a separate campaign-scope extension.

The existing registry bindings (`collectible_invoice`, `count_distinct` and `sum` aggregations) already model the Orden arithmetic correctly: they aggregate from the same `collectible_invoice` fact source that populates the Tipo 2 records. This is the canonical representation.

**Verdict: EXTRACTION-ONLY-INTRINSIC** — domain fact, not engineering gap.

### UNIT 4 — Implementation

Updated `test_verification_chain.py`:

1. Verdict table row for M349 updated from "EXTRACTION-ONLY — summary casillas only; no aggregation formulas" to "EXTRACTION-ONLY-INTRINSIC — closure totals are Tipo-2 row aggregations (Orden HAC/174/2020 Anexo pos. 138-146, 147-161, 162-170, 171-185) — not casilla-to-casilla arithmetic".

2. Module-level follow-up notes section extended with full M349 domain explanation citing Orden HAC/174/2020 Anexo.

3. Summary paragraph updated with M349 sub-classification.

4. `test_verification_chain_m349_parser_extracts_declaracion_pdf_casillas` docstring replaced with authoritative Orden HAC/174/2020 Anexo position-level arithmetic citations for all 4 casillas.

No registry TOML changes required. No new primitives introduced. No formula authored — doing so without AEAT authority for row-array aggregation in the formula DSL would violate the safety-legal gate.

### UNIT 5 — Verification

`pytest -k m349`: PASSED (1 selected, 1 passed). Adjacent regression suite (declaracion/ + test_modelo_parity_coverage.py) run in background — no failures introduced.

## Outcome

M349 stays EXTRACTION-ONLY. Sub-classification refined to EXTRACTION-ONLY-INTRINSIC with full AEAT Diseño de Registro authority. The existing `bound` casillas + `collectible_invoice` bindings are confirmed correct. No formula DSL work is possible or required at this time; the structural gap (row-array aggregation primitive) is deferred to a future campaign.
