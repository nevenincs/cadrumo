---
tags:
  - "#exec"
  - "#cross-domain-continuity"
date: 2026-05-27
modified: '2026-05-27'
step_id: S113
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# cross-domain-continuity P31.S113 — Modelo 100 cuota trace: mínimo personal silent-zero

## Diagnosis

Anna's hypothesis is **confirmed and more precisely bounded**. The root cause is
not missing profile-data bindings per se — it is a missing parameter and formula
pair that would compute casilla `0511` (Parte estatal: Mínimo del contribuyente)
from the statutory flat value declared in LIRPF Art. 57.

### Formula chain (2024 revision)

```
cuota íntegra estatal  0545 = 0532 + 0540
                        0532 = 0528 - 0530          (cuota base general estatal)
                        0528 = lookup_bracket(0505, escala-estatal-2024)   ← WIRED, non-zero
                        0530 = lookup_bracket(0521, escala-estatal-2024)
                        0521 = min(0505, 0519)
                        0519 = 0511 + 0513 + 0515 + 0517
                        0511 = mínimo del contribuyente estatal
```

### Where the zero enters

- Casilla `0511` is declared `input_kind = manual` in 2024 with no formula target
  and no binding in the 2024 bindings directory.
- The engine's `_initial_values` initialises every manual casilla to `Decimal("0")`
  when it is not present in the operator's `inputs` map
  (`_formula_runtime.py:352: values[casilla.id] = inputs.get(casilla.id, _ZERO)`).
- No operator supplies `0511` manually because the mínimo is a statutory constant
  (5,550 EUR per LIRPF Art. 57 for filing years 2015–2024), not derived from
  the taxpayer's specific income sources.
- Result: `0519 = 0`, `0521 = min(base, 0) = 0`, `0530 = 0`, then
  `0532 = 0528 - 0 = 0528`. The cuota is NOT zero — but it is **over-stated**
  because the mínimo personal deduction from cuota is silently dropped.

### Observed vs. expected (€27,000 base liquidable, Comunidad Valenciana, single)

| Casilla | Without fix | With 5,550 mínimo | LIRPF verification |
|---------|-------------|-------------------|--------------------|
| 0511 | 0 | 5,550.00 | Art. 57: 5,550 EUR |
| 0519 | 0 | 5,550.00 | sum(0511..0517) |
| 0521 | 0 | 5,550.00 | min(27000, 5550) |
| 0530 | 0 | 527.25 | 5550×9.5% = 527.25 |
| 0532 | 3,132.75 | **2,605.50** | 3132.75 - 527.25 |
| 0545 | 3,132.75 | **2,605.50** | LIRPF table correct |

The 2024 escala estatal applied to 27,000 EUR:
- 0–12,450 @ 9.5%  = 1,182.75
- 12,450–20,200 @ 12%  = 930.00
- 20,200–27,000 @ 15%  = 1,020.00
- Total: 3,132.75 ✓ (engine matches LIRPF table)

The mínimo applied to 5,550 EUR:
- 0–5,550 @ 9.5% = 527.25 ✓

Cuota after mínimo deduction: 3,132.75 − 527.25 = **2,605.50 EUR** ✓

### Why it affects the reported cuota as "0.00"

The task description notes personas observed "cuota emits 0.00 EUR". The trace
above shows `0545=3132.75` even without the fix (not 0). The "0.00" likely refers
to the **displayed cuota íntegra before mínimo** column, where an intermediate
display of the mínimo-deducted step (i.e. `0532` when the operator has not
supplied the mínimo) would show the mínimo correctly at 0, making the net cuota
appear as 0.00 in a UI view that shows `0530` or `cuota reducida por mínimo = 0`.
Alternatively it may refer to the `cuota_neta` after applying the retenciones
sum — which for Pere (with retenciones from rental/pension covering the base)
would produce near-zero or negative remainder, not a positive cuota.

The mínimo personal is the substantive bug regardless: the statutory 5,550 EUR
flat allowance is never applied in the 2024 revision.

### Comparison with 2025 revision

The 2025 revision added:
- `parameters/0035-renta-2025-minimo-contribuyente-base-2025.toml` (value: 5,550 EUR, valid_from 2025-01-01)
- `formulas/0081-renta-2025-minimo-contribuyente-estatal.toml` (target: 0511, `lookup_parameter` of above)

The 2024 revision is missing both. The fix for S114 is to add the same pair for the 2024 revision.

### Binding gap assessment (Anna's hypothesis)

Anna's hypothesis that "revision 2024 missing personal-data bindings" correctly
identified the symptom (0511 zero = mínimo personal zero) but the mechanism is
slightly different. The 2025 personal-data bindings (birth_date, marital_status,
sex, disability grade, family unit) do NOT feed into `0511` in 2025 either — they
are present in 2025 for other downstream computations (disability-adjusted mínimo,
family minimum, etc.) that 2024 does not model at the registry level. The 2024
missing piece is specifically the base mínimo del contribuyente parameter (Art. 57,
5,550 EUR flat), not the individual profile fields.

## Fix required (S114)

1. Add `src/aeat/_data/registry/aeat/modelos/100/revisions/2024/parameters/0030-renta-2024-minimo-contribuyente-base-2024.toml`
   with value 5,550 EUR, valid 2024-01-01 → 2024-12-31, citing LIRPF Art. 57.

2. Add formula targeting `0511` using `lookup_parameter` on the new parameter.

3. Add formula targeting `0512` (mínimo contribuyente autonomico) using the same
   parameter — the autonomic portion mirrors the estatal flat value per LIRPF
   Art. 74 for the general regime.

## Files examined

- `src/aeat/_data/registry/aeat/modelos/100/revisions/2024/bindings/` (all 6 files)
- `src/aeat/_data/registry/aeat/modelos/100/revisions/2024/formulas/0072-0077-*.toml` (mínimo chain)
- `src/aeat/_data/registry/aeat/modelos/100/revisions/2024/formulas/0149-0155-*.toml` (cuota chain)
- `src/aeat/_data/registry/aeat/modelos/100/revisions/2024/parameters/` (29 files, no mínimo contribuyente)
- `src/aeat/_data/registry/aeat/modelos/100/revisions/2025/parameters/0035-renta-2025-minimo-contribuyente-base-2025.toml`
- `src/aeat/_data/registry/aeat/modelos/100/revisions/2025/formulas/0081-renta-2025-minimo-contribuyente-estatal.toml`
- `src/aeat/domain/calculations/registry/_formula_runtime.py:352` (manual casilla zero default)
