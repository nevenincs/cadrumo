---
step_id: S113
tags:
  - "#exec"
  - "#cross-domain-continuity"
date: 2026-05-27
modified: '2026-05-27'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
  - "[[2026-05-26-cross-domain-continuity-W07-P31-S114]]"
  - "[[2026-05-26-cross-domain-continuity-W07-P31-S115]]"
---

# cross-domain-continuity W07.P31.S113 — Modelo 100 cuota trace: mínimo personal silent-zero

## Outcome

Root cause identified and documented. See full trace below.

Commit: `01ac9d698` (combined S113+S114)

## Diagnosis

Anna's hypothesis is confirmed and more precisely bounded. The root cause is
not missing profile-data bindings per se — it is a missing parameter and formula
pair that would compute casilla `0511` (Parte estatal: Mínimo del contribuyente)
from the statutory flat value declared in LIRPF Art. 57.

### Formula chain (2024 revision)

```
cuota íntegra estatal  0545 = 0532 + 0540
                        0532 = 0528 - 0530          (cuota base general estatal)
                        0528 = lookup_bracket(0505, escala-estatal-2024)   <- WIRED, non-zero
                        0530 = lookup_bracket(0521, escala-estatal-2024)
                        0521 = min(0505, 0519)
                        0519 = 0511 + 0513 + 0515 + 0517
                        0511 = mínimo del contribuyente estatal
```

### Where the zero enters

- Casilla `0511` is declared `input_kind = manual` in 2024 with no formula target
  and no binding in the 2024 bindings directory.
- The engine's `_initial_values` initialises every manual casilla to `Decimal("0")`
  when not present in the operator's `inputs` map
  (`_formula_runtime.py:352: values[casilla.id] = inputs.get(casilla.id, _ZERO)`).
- No operator supplies `0511` manually because the mínimo is a statutory constant
  (5,550 EUR per LIRPF Art. 57 for filing years 2015-2024), not derived from
  the taxpayer's income.
- Result: `0519 = 0`, `0521 = min(base, 0) = 0`, `0530 = 0`, then
  `0532 = 0528 - 0 = 0528`. The cuota is over-stated because the mínimo personal
  deduction from cuota is silently dropped.

### Observed vs. expected (EUR 27,000 base liquidable, Comunidad Valenciana, single)

| Casilla | Without fix | With 5,550 minimo | LIRPF verification |
|---------|-------------|-------------------|--------------------|
| 0511 | 0 | 5,550.00 | Art. 57: 5,550 EUR |
| 0519 | 0 | 5,550.00 | sum(0511..0517) |
| 0521 | 0 | 5,550.00 | min(27000, 5550) |
| 0530 | 0 | 527.25 | 5550 x 9.5% = 527.25 |
| 0532 | 3,132.75 | 2,605.50 | 3132.75 - 527.25 |
| 0545 | 3,132.75 | 2,605.50 | LIRPF table correct |

### Comparison with 2025 revision

The 2025 revision added:
- `parameters/0035-renta-2025-minimo-contribuyente-base-2025.toml` (value: 5,550 EUR)
- `formulas/0081-renta-2025-minimo-contribuyente-estatal.toml` (target: 0511, `lookup_parameter`)

The 2024 revision was missing both. The fix (S114) adds the same pair for 2024.

## Files examined

- `src/aeat/_data/registry/aeat/modelos/100/revisions/2024/bindings/` (all 6 files)
- `src/aeat/_data/registry/aeat/modelos/100/revisions/2024/formulas/0072-0077-*.toml` (minimo chain)
- `src/aeat/_data/registry/aeat/modelos/100/revisions/2024/formulas/0149-0155-*.toml` (cuota chain)
- `src/aeat/_data/registry/aeat/modelos/100/revisions/2024/parameters/` (29 files, no minimo contribuyente)
- `src/aeat/_data/registry/aeat/modelos/100/revisions/2025/parameters/0035-renta-2025-minimo-contribuyente-base-2025.toml`
- `src/aeat/_data/registry/aeat/modelos/100/revisions/2025/formulas/0081-renta-2025-minimo-contribuyente-estatal.toml`
- `src/aeat/domain/calculations/registry/_formula_runtime.py:352` (manual casilla zero default)
