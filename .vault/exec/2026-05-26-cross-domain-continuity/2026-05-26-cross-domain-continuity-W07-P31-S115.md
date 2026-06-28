---
step_id: S115
tags:
  - "#exec"
  - "#cross-domain-continuity"
date: 2026-05-27
modified: '2026-05-27'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
  - "[[2026-05-27-s113-modelo-100-cuota-trace-exec]]"
---

# cross-domain-continuity W07.P31.S115 — Cluster T regression test

## Outcome

Regression test written and passing (4/4) at
`src/aeat/domain/calculations/registry/test_modelo_100_tarifa_real.py`.

Commit: `65a0bc0dd`

## What was done

Added four pytest tests using a Pere-shape profile (single taxpayer, Cataluña,
base liquidable general 35,400 EUR, no ahorro base) to guard against the
Cluster T silent-zero defect fixed in S114.

Expected values are derived from the published LIRPF 2024 tax tables — not
from re-running the formula engine — satisfying the anti-tautological test
mandate:

| Casilla | Meaning | Expected (LIRPF table) |
|---------|---------|------------------------|
| 0511 | Mínimo contribuyente estatal | 5,550.00 EUR |
| 0512 | Mínimo contribuyente autonómica | 5,550.00 EUR |
| 0545 | Cuota íntegra estatal | 3,872.50 EUR |
| 0546 | Cuota íntegra autonómica (Cataluña) | 4,067.28 EUR |

LIRPF derivation embedded in test module docstring and constants block for
auditability (Art. 57, 62-63, 74-75; escala estatal 2024 + Ley 5/2020
Cataluña).

## Authority

Expected values derived from:
- LIRPF Art. 63 escala estatal 2024 (9.5 / 12 / 15 / 18.5 %)
- LIRPF Art. 57 mínimo del contribuyente (5,550 EUR flat, unchanged 2024)
- Cataluña 2024 autonomic escala (Ley 5/2020: 10.5 / 12 / 14 / 15 / 18.8 %)
- AEAT Renta 2024 Manual, Part 1 "Liquidación del impuesto"
- BOE Orden HAC-563-2024 (5,550 EUR confirmed unchanged for 2024)

## Files changed

- `src/aeat/domain/calculations/registry/test_modelo_100_tarifa_real.py` (NEW, 202 lines)
