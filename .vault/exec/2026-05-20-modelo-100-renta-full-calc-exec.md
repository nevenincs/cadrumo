---
tags:
  - '#exec'
  - '#modelo-100-renta-full-calc'
date: '2026-05-20'
modified: '2026-05-20'
step_id: 'S01'
related:
  - "[[2026-04-27-modelo-100-renta-full-calc-adr]]"
---

# `modelo-100-renta-full-calc` `S01`

Authored the IRPF art.66 ahorro-base estatal progressive scale (escala
del ahorro, parte estatal) as Modelo 100 registry data for ejercicios
2020 through 2025, closing a latent defect where casillas `0536`,
`0538`, and `0540` carried `ley-35-2006:art-66` legal grounding but no
formula produced them, leaving downstream `0542` and `0545` silently
zero for the savings-base contribution.

## Description

The shipped M100 registry declared three savings-base estatal casillas
with art.66 in their `legal_refs` but no producer: `0536`
(`irpf_escala_sobre_base_ahorro_estatal`), `0538`
(`irpf_escala_sobre_minimo_ahorro_estatal`), `0540`
(`irpf_cuota_base_liquidable_ahorro_estatal`). Downstream formulas for
`0542` (tipo medio de gravamen estatal del ahorro) and `0545` (cuota
íntegra estatal) consumed `0540` as if populated.

The fix mirrors the already-shipped general-base estatal escala. Per
ejercicio a `bracket_table` parameter `renta-{year}-escala-estatal-base-ahorro`
was added, plus three formulas: `0536` via `lookup_bracket` on `0510`
(base liquidable del ahorro), `0538` via `lookup_bracket` on `0522`
(mínimo personal y familiar imputado a la base del ahorro), and `0540`
via `subtract([0536], [0538])`. The three casilla TOMLs were promoted
to `input_kind = "computed"` with their `formula` field, and the
`renta-cuota-chain` construct's `formulas` list was extended in each
revision so the new formulas are construct-owned.

### Bracket tables and BOE/AEAT source

Brackets are grounded against the AEAT *Manual práctico de Renta*,
section "Gravamen de la base liquidable del ahorro — Gravamen estatal —
Normativa: Art. 66.1 Ley IRPF", cross-checked against the BOE
consolidated text of art.66 Ley 35/2006 (`BOE-A-2006-20764`,
corpus `corpus/normatives/html/ley-35-2006.html`). The estatal savings
tariff was amended across ejercicios: Ley 11/2020 added the >200.000
tier (effective 2021), Ley 31/2022 added the >300.000 tier (effective
2023), Ley 7/2024 raised the top tier (effective 2025).

- 2020 — Manual Renta 2020 Parte 1, page 895. Three brackets:
  0–6.000 @ 9,5% (incremento 0); 6.000–50.000 @ 10,5% (570);
  >50.000 @ 11,5% (5.190).
- 2021 — Manual Renta 2021 Parte 1, page 919. Four brackets:
  0–6.000 @ 9,5% (0); 6.000–50.000 @ 10,5% (570);
  50.000–200.000 @ 11,5% (5.190); >200.000 @ 13% (22.440).
- 2022 — Manual Renta 2022 Parte 1, page 982. Same four brackets and
  rates as 2021.
- 2023 — Manual Renta 2023 Parte 1, page 1152. Five brackets:
  0–6.000 @ 9,5% (0); 6.000–50.000 @ 10,5% (570);
  50.000–200.000 @ 11,5% (5.190); 200.000–300.000 @ 13,5% (22.440);
  >300.000 @ 14% (35.940).
- 2024 — Manual Renta 2024 Parte 1, page 1245. Same five brackets and
  rates as 2023.
- 2025 — Manual Renta 2025 Parte 1, page 953. Five brackets:
  0–6.000 @ 9,5% (0); 6.000–50.000 @ 10,5% (570);
  50.000–200.000 @ 11,5% (5.190); 200.000–300.000 @ 13,5% (22.440);
  >300.000 @ 15% (35.940). The top rate rise to 15% is the Ley 7/2024
  (disp. final 7.1, `BOE-A-2024-26694`) amendment.

The "Incremento en cuota íntegra estatal" values (0, 570, 5.190,
22.440, 35.940) are the AEAT-published cumulative cuotas at each
breakpoint and become the `fixed_addition` of each bracket. Internal
consistency was checked: each `fixed_addition` equals the prior
bracket's `fixed_addition + marginal_rate × bracket_width`.

### Formulas authored

- `renta-{year}-cuota-escala-estatal-sobre-base-liquidable-ahorro` →
  target `0536`, op `lookup_bracket([0510], renta-{year}-escala-estatal-base-ahorro)`.
- `renta-{year}-cuota-escala-estatal-sobre-minimo-personal-familiar-base-ahorro`
  → target `0538`, op `lookup_bracket([0522], renta-{year}-escala-estatal-base-ahorro)`.
- `renta-{year}-cuota-base-liquidable-ahorro-estatal` → target `0540`,
  op `subtract([0536], [0538])`.

Every parameter and formula carries `ley-35-2006:art-66` in
`legal_refs` (catalogued at `aeat/legal/irpf.toml`); the 2025 formulas
additionally carry `orden-hac-277-2026:art-3` and `ley-35-2006:art-56`
where applicable, matching the shipped general-escala convention.
Parameters carry `source_refs = ["lirpf-cuota-chain-authority"]`; 2025
formulas carry `aeat-renta-2025-manual-parte1` and
`boe-modelo-100-2025-form`; backport formulas carry
`lirpf-cuota-chain-authority`. All are catalogued sources.

## Tests

A calc-verify test was added at
`test_renta_escala_estatal_ahorro_bracket_resolution.py` (48 cases,
all green). The external oracle is the worked example on AEAT Manual
Renta 2025 Parte 1, page 954 ("Don A.B.C., residente en Aragón"): base
liquidable del ahorro 2.800 EUR, mínimo absorbed in full by the
general base, so `0522 = 0` — the manual states "Gravamen estatal
2.800 x 9,50% = 266". The test asserts `0540` resolves to 266 EUR for
every ejercicio (the 9,5% first-bracket rate is stable across all
covered years), and asserts the published "Incremento en cuota íntegra
estatal" at each breakpoint (570, 5.190, 22.440, 35.940). Expected
values are transcribed from AEAT authority, never computed from the
registry formula under test, satisfying the
no-tautological-calculation-tests rule.

Two pre-existing scenario tests that supplied `0540` as a manual input
were corrected: `test_renta_chain_behaviour.py` (`_base_2025_inputs`)
and `test_registry_scenarios.py` (`_final_settlement_scenario`) — both
dropped the now-illegal `0540` input, mirroring how `0528`–`0531` were
handled when the general escala became computed.

Verified green: `test_referential_integrity.py`,
`test_formula_runtime.py`, `test_modelo_parity_coverage.py`,
`test_registry_schema.py`, `test_renta_chain_behaviour.py`,
`test_modelo_100_autonomic_chain.py`,
`test_renta_escala_estatal_bracket_resolution.py`, and the new
ahorro-escala test (228 + 48 passed). The full registry tree loads
with all 26 modelos valid; `0540` is now produced and downstream
`0542`/`0545` read it. `ruff check` clean on all modified files.

Two unrelated pre-existing failures remain in the Modelo 200
`2024-y-siguientes` revision (`test_formula_modelo_registry_parity`,
`test_cross_dependency_contract`, and a `test_modelo_200_registry`
tautology check) — caused by a concurrent Modelo 200 page-14 cuota
chain campaign (commit `aae1bb60c`), touching no file in this change
set.
