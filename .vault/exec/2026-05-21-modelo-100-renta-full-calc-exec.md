---
tags:
  - '#exec'
  - '#modelo-100-renta-full-calc'
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'S02'
related:
  - "[[2026-04-27-modelo-100-renta-full-calc-adr]]"
---

# `modelo-100-renta-full-calc` `S02`

Authored the IRPF art.76 ahorro-base autonómica progressive scale
(escala autonómica del ahorro) as Modelo 100 registry data for
ejercicios 2020 through 2025 — the autonómica counterpart of the
art.66 ahorro-base estatal escala. This closes a latent defect where
casillas `0537`, `0539`, and `0541` carried savings-base autonómica
labels but no formula produced them, leaving the autonómica savings
contribution to `0543` (tipo medio autonómico del ahorro) and the
cuota íntegra autonómica silently zero.

## Description

The shipped M100 registry declared three savings-base autonómica
casillas as manual inputs: `0537`
(`irpf_escala_general_resultado_autonomico`), `0539`
(`irpf_escala_sobre_minimo_ahorro_autonomico`), `0541`
(`irpf_cuota_base_liquidable_ahorro_autonomico`). The shipped
formula `0543` (tipo medio de gravamen autonómico de la base del
ahorro) already consumed `0541` as if populated.

The fix mirrors the art.66 ahorro-base estatal chain exactly, for
the autonómica half. Per ejercicio a `bracket_table` parameter
`renta-{year}-escala-autonomica-base-ahorro` was added, plus three
formulas: `0537` via `lookup_bracket` on `0510` (base liquidable del
ahorro), `0539` via `lookup_bracket` on `0524` (importe del mínimo
personal y familiar que forma parte de la base liquidable del ahorro
a efectos del cálculo del gravamen autonómico), and `0541` via
`subtract([0537], [0539])`. The three casilla TOMLs were promoted to
`input_kind = "computed"` with their `formula` field, and the
`renta-cuota-chain` construct's `formulas` list plus its `legal_refs`
(`ley-35-2006:art-76`) were extended in every revision.

A key correction against the originating brief: the autonómica
escala-sobre-mínimo formula (`0539`) takes casilla `0524`, the
**autonómica** mínimo imputado a la base del ahorro, not `0522`
(the estatal mínimo). Casilla `0524` carries
`semantic_role = "irpf_minimo_aplicado_base_ahorro_autonomico"` in
every revision and the `0539` casilla label itself references
`[0524]`; using `0522` would have minorado the autonómica cuota by
the estatal mínimo. The base (`0510`) is shared by both halves; only
the mínimo casilla differs (estatal `0522`, autonómica `0524`).

### BOE grounding — art.76 brackets equal the art.66 estatal scale

The autonómica savings scale is fixed by state law, not legislated
per-CCAA. Art.76 Ley 35/2006 ("Tipo de gravamen del ahorro")
provides a single statutory scale; unlike the general base (where
CCAA set their own scales, handled in the registry via
`lookup_bracket_by_ccaa` dispatch tables), the savings base
autonómica scale is a single `bracket_table` resolved with plain
`lookup_bracket`, identical in shape to the estatal ahorro chain.

The per-ejercicio art.76 brackets were transcribed from the AEAT
*Manual práctico de Renta*, section "Gravamen de la base liquidable
del ahorro — Gravamen autonómico — Normativa: Art. 76 Ley IRPF",
cross-checked against the BOE consolidated text of art.76 Ley
35/2006 (`BOE-A-2006-20764`, corpus
`corpus/normatives/html/ley-35-2006.html`). The art.76 footnotes
confirm it was amended by exactly the same three laws as art.66:
Ley 11/2020 (>200.000 tier, effective 2021), Ley 31/2022 (>300.000
tier, effective 2023), Ley 7/2024 (top rate 15%, effective 2025).

For every ejercicio 2020–2025 the art.76 autonómica savings brackets
are **bracket-identical** to the art.66.1 estatal savings brackets:

- 2020 (3 brackets): 0–6.000 @ 9,5% (0); 6.000–50.000 @ 10,5%
  (570); >50.000 @ 11,5% (5.190). Manual Renta 2020 Parte 1.
- 2021–2022 (4 brackets): 0–6.000 @ 9,5% (0); 6.000–50.000 @ 10,5%
  (570); 50.000–200.000 @ 11,5% (5.190); >200.000 @ 13% (22.440).
  Manual Renta 2021/2022 Parte 1.
- 2023–2024 (5 brackets): 0–6.000 @ 9,5% (0); 6.000–50.000 @ 10,5%
  (570); 50.000–200.000 @ 11,5% (5.190); 200.000–300.000 @ 13,5%
  (22.440); >300.000 @ 14% (35.940). Manual Renta 2023/2024 Parte 1.
- 2025 (5 brackets): same as 2023/2024 except the top tier rises to
  15% (35.940). Manual Renta 2025 Parte 1, page 953. The 15% top
  rate is the Ley 7/2024 (disp. final 7.2, `BOE-A-2024-26694`)
  amendment.

Because the art.76 brackets are confirmed identical to the estatal
ones, the exact estatal values were reused. The "Incremento en cuota
íntegra" column (0, 570, 5.190, 22.440, 35.940) is the AEAT-published
cumulative cuota at each breakpoint and becomes each bracket's
`fixed_addition`.

### Catalogue additions

`ley-35-2006:art-76` was not previously catalogued. It was added to
the shared legal catalogue (`aeat/legal/irpf.toml`) as a
`legal_authority`/`boe` reference, and a matching `art-76` article
entry was added to the corpus JSON `corpus/normatives/ley-35-2006.json`
(four-language summary/título, mirroring art-66/art-75). Parameters
carry `source_refs = ["lirpf-cuota-chain-authority"]`; 2020–2024
formulas carry the same; 2025 formulas carry
`aeat-renta-2025-manual-parte1` + `boe-modelo-100-2025-form` and
`orden-hac-277-2026:art-3`, matching the shipped estatal 2025
convention. All sources and legal refs are catalogued.

### Formulas authored

- `renta-{year}-cuota-escala-autonomica-sobre-base-liquidable-ahorro`
  → target `0537`, op
  `lookup_bracket([0510], renta-{year}-escala-autonomica-base-ahorro)`.
- `renta-{year}-cuota-escala-autonomica-sobre-minimo-personal-familiar-base-ahorro`
  → target `0539`, op
  `lookup_bracket([0524], renta-{year}-escala-autonomica-base-ahorro)`.
- `renta-{year}-cuota-base-liquidable-ahorro-autonomica` → target
  `0541`, op `subtract([0537], [0539])`.

## Tests

A calc-verify test was added at
`test_renta_escala_autonomica_ahorro_bracket_resolution.py` (66
cases, all green). The external oracle is the worked example on AEAT
Manual Renta 2025 Parte 1, page 954 ("Don A.B.C., residente en
Aragón"): base liquidable del ahorro 2.800 EUR, mínimo absorbed in
full by the general base — the manual states "Gravamen autonómico
2.800 x 9,50% = 266". The test asserts the autonómica escala resolves
`2.800` to `266` for every ejercicio, asserts the published
"Incremento en cuota íntegra" breakpoint values (570, 5.190, 22.440,
35.940), and includes a structural guard
(`test_ahorro_escala_matches_estatal_scale`) that the art.76 brackets
equal the art.66 estatal brackets every year — the BOE finding that
drove this work. Expected values are AEAT-published, never recomputed
from the registry formula under test, satisfying the
no-tautological-calculation-tests rule.

Two pre-existing scenario fixtures that supplied `0541` as a manual
input were corrected: `test_renta_chain_behaviour.py`
(`_base_2025_inputs`) and `test_registry_scenarios.py`
(`modelo-100-2025-final-settlement` scenario) — both dropped the
now-illegal `0541` input, mirroring how `0540` was handled when the
estatal escala became computed. Neither test asserts `0541` or its
downstream casillas.

Verified green: `test_referential_integrity.py` (46),
`test_formula_runtime.py` + `test_registry_schema.py` (81),
`test_catalogue_verification.py` (31), `test_renta_chain_behaviour.py`
+ `test_modelo_parity_coverage.py` + `test_registry_scenarios.py`
(8), `test_modelo_100_autonomic_chain.py` (66),
`test_renta_cuota_chain_contract.py` + `test_modelo_chain_cohesion.py`
+ `test_modelo_chain_resolution.py` (20), and the new autonómica
ahorro-escala test (66). The full registry tree loads with all 26
modelos valid; `0541` is now `input_kind = computed` in every M100
revision and downstream `0543` reads it. `ruff check` clean on all
modified files.
