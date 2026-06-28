---
step_id: S361
tags:
  - "#exec"
  - "#cross-domain-continuity"
date: 2026-05-27
modified: '2026-05-27'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# cross-domain-continuity W07.P31.S361 — M100 2024 final-settlement chain

## Outcome

Six missing formulas and their associated casilla bindings were authored for the
M100 2024 settlement tail, stopping the silent-zero failure for casillas 0587,
0595, 0598, 0609, 0610, and 0670.

## Commits

- `17cea3fe8` — TOML: 6 new formula files (0169–0174), 1 new construct
  (`renta-2024-final-settlement`), 6 casilla TOMLs flipped to
  `input_kind = "computed"`
- `8fa4b6fc9` — Tests: 4 structural identity regression tests for the
  settlement chain

## Artefacts produced

### New formula TOMLs (`revisions/2024/formulas/`)

| File | Formula ID | Target |
|------|-----------|--------|
| `0169-renta-2024-cuota-liquida-incrementada-total.toml` | `renta-2024-cuota-liquida-incrementada-total` | 0587 |
| `0170-renta-2024-cuota-resultante-autoliquidacion.toml` | `renta-2024-cuota-resultante-autoliquidacion` | 0595 |
| `0171-renta-2024-retenciones-arrendamientos-urbanos.toml` | `renta-2024-retenciones-arrendamientos-urbanos` | 0598 |
| `0172-renta-2024-total-pagos-a-cuenta.toml` | `renta-2024-total-pagos-a-cuenta` | 0609 |
| `0173-renta-2024-cuota-diferencial.toml` | `renta-2024-cuota-diferencial` | 0610 |
| `0174-renta-2024-resultado-declaracion.toml` | `renta-2024-resultado-declaracion` | 0670 |

### New construct TOML

`constructs/0011-renta-2024-final-settlement.toml` — groups the 6 formulas
under `application_links` for `modelo-100-2024-calculation/verification/workflow`.
Includes `lirpf-cuota-chain-authority` in `source_refs` (required by the
application_link validation gate).

### Casilla TOMLs modified

`0569-0587.toml`, `0577-0595.toml`, `0580-0598.toml`, `0591-0609.toml`,
`0592-0610.toml`, `0651-0670.toml` — each gained `input_kind = "computed"` and
the matching `formula =` binding.

### Tests

`src/aeat/domain/calculations/registry/test_modelo_100_tarifa_real.py`:

- `test_s361_0587_equals_sum_of_liquida_incrementada` — identity: 0587 = 0585 + 0586
- `test_s361_0609_equals_retencion_trabajo_operand` — identity: 0609 = sum(operands), verified via single-operand probe
- `test_s361_0610_equals_0595_minus_0609` — identity: 0610 = 0595 - 0609
- `test_s361_anti_tautology_higher_retencion_reduces_cuota_diferencial` — anti-tautology: doubling retención halves the differential, delta is exact

## Key design decision

Casilla 0414 ("Deducción por obtención de rendimientos del trabajo") was
intentionally omitted from the 0595 expression. The casilla does not exist in
the 2024 registry revision; it was introduced in 2025. The 2024 casilla label
for 0595 confirms the 5-operand form: `[0587] - [0588] - [0589] - [0590] - [0591]`.

## Quality gates

- `ruff check` clean on all modified files
- `mypy` clean
- All 14 tests in `test_modelo_100_tarifa_real.py` pass
- Registry snapshot builds without validation errors
- `vault plan step check` closed S361 via CLI (no hand-editing)
