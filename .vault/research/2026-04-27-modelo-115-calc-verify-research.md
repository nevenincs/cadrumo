---
tags:
  - '#research'
  - '#modelo-115-calc-verify'
date: '2026-04-27'
modified: '2026-04-27'
related:
  - "[[2026-04-27-modelo-130-calc-verify-research]]"
  - "[[2026-04-27-modelo-130-calc-verify-adr]]"
  - "[[2026-04-27-modelo-130-rule-delta-reference]]"
---

# `modelo-115-calc-verify` research

EPIC `#316` per-modelo Tier-L calc-verify-roundtrip umbrella;
issue `#319` is the fourth delegation under that umbrella, after
`#321` (Modelo 130 — landed reference implementation), `#326`
(Modelo 303 — in flight), `#322` (Modelo 131 — in flight). This
research grounds the 2024 → 2025 → 2026 trail for Modelo 115
(retención IRPF sobre arrendamientos urbanos, trimestral) so the
ADR can pin every numerical and structural decision to a primary
source.

## Statutory grounding

Modelo 115 is the quarterly autoliquidación of the IRPF retención
that the **lessee** withholds and remits when paying rent for
**urban real estate** to a non-corporate landlord. The numerical
surface is fixed by:

| Reference                                                     | Role                                                                       | BOE id              |
| :------------------------------------------------------------ | :------------------------------------------------------------------------- | :------------------ |
| Ley 35/2006 IRPF (LIRPF) art. 99                              | General obligation to make pagos a cuenta                                  | `BOE-A-2006-20764`  |
| LIRPF art. 101.8                                              | Hooks the obligation to retain on rendimientos del capital inmobiliario    | `BOE-A-2006-20764`  |
| LIRPF art. 68.4                                               | Hosts the Ceuta / Melilla 60 % deducción referenced from RIRPF art. 100 § 2 | `BOE-A-2006-20764`  |
| Real Decreto 439/2007 (RIRPF) art. 100                        | Numerical surface of Modelo 115 — fixes 19 % retention on arrendamientos urbanos and the Ceuta / Melilla 60 % reduction | `BOE-A-2007-6820`   |
| Orden EHA/1658/2009                                           | Modelo 115 form layout (six-casilla liquidación block)                     | `BOE-A-2009-10295`  |

The RIRPF consolidated text last update is **2026-02-28**. The PDF
(`https://www.boe.es/buscar/pdf/2007/BOE-A-2007-6820-consolidado.pdf`)
was retrieved 2026-04-27 for this research and verifies the verbatim
art. 100 surface.

### Verbatim BOE text (2026-02-28 consolidated, art. 100)

> **Artículo 100. Importe de las retenciones sobre arrendamientos
> y subarrendamientos de inmuebles.**
>
> La retención a practicar sobre los rendimientos procedentes del
> arrendamiento o subarrendamiento de inmuebles urbanos, cualquiera
> que sea su calificación, será el resultado de aplicar el
> porcentaje del 19 por ciento sobre todos los conceptos que se
> satisfagan al arrendador, excluido el Impuesto sobre el Valor
> Añadido.
>
> Este porcentaje se reducirá en el 60 por ciento cuando el inmueble
> urbano esté situado en Ceuta o Melilla, en los términos previstos
> en el artículo 68.4 de la Ley del Impuesto.

Two unnumbered paragraphs. The wave-67g/68 correction recorded in
the existing `test_modelo_115_2025.py` flagged that referencing
`100.3.a` was wrong; the existing 2025 ruleset cites `100.1` (the
first paragraph — the rate clause). We retain that convention.

## Per-year numerical state

| Element                                                       | 2024              | 2025              | 2026              | Source                  |
| :------------------------------------------------------------ | :---------------- | :---------------- | :---------------- | :---------------------- |
| Retención rate on arrendamientos urbanos (casilla 03)         | 19 %              | 19 %              | 19 %              | RIRPF art. 100, ¶ 1     |
| Ceuta / Melilla reducción aplicable (caller-gated overlay)    | 60 %              | 60 %              | 60 %              | RIRPF art. 100, ¶ 2     |
| Number of computed casillas (03 + 06)                         | 2                 | 2                 | 2                 | Orden EHA/1658/2009     |
| Number of user-supplied casillas (01, 02, 04, 05)             | 4                 | 4                 | 4                 | Orden EHA/1658/2009     |
| Total casillas (form coverage)                                | 6                 | 6                 | 6                 | Orden EHA/1658/2009     |
| IVA exclusion from base (verifies "excluido el IVA" rule)     | active            | active            | active            | RIRPF art. 100, ¶ 1     |

## 2024 → 2025 diff narrative

**No amendment.** The existing 2024 ruleset
(`src/aeat/domain/formulas/_rulesets/modelo_115_2024.py`) re-imports
`_CASILLAS`, `_FORMULAS`, and `_CITATIONS` from the 2025 module and
declares only its own `_PARAMETERS` with the 2024 effective range.
The numerical content is identical: `irpf.arrendamientos_rate =
Decimal("0.19")`. The wave-29/48 audit history in the codebase
already documents this.

Source: BOE-consolidated text of RD 439/2007 art. 100 (last update
2026-02-28) carries no 2024 modification notice for art. 100. The
listed 2024 modificaciones (07/02/2024, 31/01/2024) do not touch
the 100 series.

## 2025 → 2026 diff narrative

**No amendment.** The 2026 ruleset will be a structural and
numerical clone of the 2024 / 2025 rulesets. The list of
modificaciones to RD 439/2007 enumerated in the consolidated text
sidebar is:

- 28/02/2026 (latest)
- 04/02/2026
- 28/01/2026
- 24/12/2025
- 02/04/2025
- 07/02/2024
- 31/01/2024

The 2025 modification is **RD 253/2025** (de 1 de abril). The
companion `2026-04-27-modelo-130-rule-delta-reference` manifest authored under issue
`#321` already verified that RD 253/2025 modifies RIRPF art. 69
(information obligations) — not art. 100 nor art. 110. The four
2026 dates touch sections of the reglamento that do not include
art. 100 (the verbatim art. 100 text quoted above is the
post-consolidation surface and has no modification footnote
attached).

The 2026 ruleset file will re-import `_CASILLAS_2025`,
`_FORMULAS_2025`, and `_CITATIONS_2025` from the 2025 module and
declare its own `_PARAMETERS` with `effective_from=2026-01-01` /
`effective_to=2026-12-31`, mirroring the existing 2024 / 2025 clone
pattern.

## M115 Formula node distribution

The casilla map (per Orden EHA/1658/2009 + the existing 2025
ruleset):

- **01** Nº de arrendadores — user-supplied (count, not Decimal in
  semantics but stored as Decimal for engine uniformity)
- **02** Base de retención — user-supplied
- **03** Retenciones e ingresos a cuenta — **computed**: `19 % × 02`
- **04** Ingresos a cuenta por retribución en especie — user-supplied
- **05** A deducir: exclusivamente en declaración complementaria —
  user-supplied
- **06** Resultado a ingresar — **computed**: `03 + 04 - 05`

The Formula node fingerprint per ruleset (verified at the engine
level by `test_mutator_kill_rate.EXPECTED_COUNTS`):

| Mutator class               | Count per ruleset |
| :-------------------------- | :----------------: |
| `sub_op`                    | 1                  |
| `percent_rate_param`        | 1                  |
| `percent_rate_literal`      | 0                  |
| `brackets_threshold`        | 0                  |
| `mul_div_scalar`            | 0                  |
| **Total mutable nodes**     | **2**              |

This is the **smallest mutable surface of any IRPF Tier-L modelo**
— smaller than M111 (3), M130 (10), M131 (7), M303 (7). The Tier-L
mutation kill-rate floor is ≥ 90 %; on 2 nodes the harness is at
100 % per the existing `test_operand_swap_mutation` (casilla 06
sub_op chain, M115 fixture) + `test_percent_rate_mutation`
(casilla 03 percent rate, M115 fixture). The 2026 ruleset clones
that fingerprint verbatim.

## Existing surface — pre-issue baseline

The 2026-04-22 audit and the 2026-04-25 EPIC `#316` snapshot agree
on the M115 baseline:

- **Ruleset 2024** — `modelo_115_2024.py`. Re-import-clone of 2025;
  citation coverage 100 % (audited by `aeat audit rulesets
  citations`).
- **Ruleset 2025** — `modelo_115_2025.py`. Canonical surface; ships
  `_CASILLAS`, `_FORMULAS`, `_CITATIONS`. Citation coverage 100 %.
- **Extractor** — `Modelo115V2025Extractor` in
  `src/aeat/adapters/inbound/declaracion/_extractors/modelo_115_v2025.py`. Six
  casillas (`01..06`). Subclass of `GenericDeclaracionExtractor`.
- **Per-ruleset tests** — `test_modelo_115_2025.py` ships the canonical
  five test cases (clean audit, percent mismatch, resultado-formula,
  citations contract, external worked example). The 2024 ruleset is
  exercised via `test_backfill_2024_rulesets.py::TestModelo1152024`
  with two cases (clean + wrong-rate). No dedicated 2024 test file.
- **Integration** — `tests/integration/test_kent_workflows.py::TestKentImportsModelo115Declaracion`
  ships the four mandatory cases (English happy / Spanish happy /
  partial / discrepancy classifier). The `test_discrepancy_classified_correctly`
  case is **already wired** — drift `c03=9999` produces
  `CORRECTNESS_DIVERGENCE`.
- **Mutation harness** — `test_mutator_kill_rate.EXPECTED_COUNTS`
  has rows for `modelo_115.2024` and `modelo_115.2025` at
  `sub_op=1, percent_rate_param=1`. The percent-rate harness has
  cases for both years (`test_percent_rate_mutation._ruleset_cases`).
  The operand-swap harness has a `_modelo_115_fixture` exercising
  the 2025 casilla-06 sub_op (no 2024 case — the wave-75a fixture
  attaches to the 2025 ruleset).
- **Synthetic generator** — quarterly PDFs are rendered by the
  shared `QuarterlyGenParams` / `generate_quarterly` helpers under
  `aeat.domain.testing`. M115 is exercised through the
  `_synth_quarterly_pdf` integration helper. No bespoke generator
  needed (M115 fits the generic 6-casilla quarterly shape).

## Identified gaps (issue `#319` scope)

1. **No 2026 ruleset.** Author `modelo_115_2026.py` as a structural
   clone of 2025; register `MODELO_115_2026` in the rulesets
   package `__init__.py`.
2. **No 2024 / 2026 declaración extractor sibling classes.** The
   registry currently keys M115 only on `(modelo="115", año=2025,
   revision="2025.01")`. A 2024 or 2026 declaración PDF would raise
   `NoExtractorRegisteredError`. Mirror the M130 fix (`#321` PR
   #440 post-review): add `Modelo115V2024Extractor` and
   `Modelo115V2026Extractor` sibling classes pinning their own
   `template_revision` ClassVars.
3. **No `2026-115-rule-delta.md`.** Author the rule-delta manifest
   with statutory grounding, per-year numerical state, diff
   narratives, mutation fingerprint, and L1 waiver — mirroring the
   `2026-130-rule-delta.md` structure exactly.
4. **No L1 anchor decision** for M115. Document the same waiver
   reasoning as M130 (AEAT publishes no normative specimen
   declaración; private autoliquidación; Manual práctico carries
   only worked examples in prose, not the printed PDF declaración).
5. **No per-year worked example for 2026.** Author
   `test_modelo_115_2026.py` mirroring `test_modelo_130_2026.py`:
   a clean audit, a no-drift assertion against the 2025 ruleset on
   the same fixture, an external-anchored worked example whose
   expected values come from RIRPF art. 100 verbatim, and a
   negative-path retention-mismatch test.
6. **No threshold-edge test for 2024.** Adding a dedicated
   `test_modelo_115_2024.py` is **out of scope** — the existing
   `test_backfill_2024_rulesets.py::TestModelo1152024` shape is the
   project convention for 2024 backfill rulesets across all the
   non-130 IRPF modelos (111, 115, 123, 131, 180). Diverging on a
   single year would introduce drift the kill-rate harness already
   disallows (per the M130 ADR §D4 and the existing
   `test_backfill_2024_rulesets.py` boundary). Reuse the existing
   pattern.
7. **Per-year integration test parametrisation.** Add the same
   `test_per_year_happy_path_verified` parametrised case M130
   ships, asserting the CLI verdict resolves to `VERIFIED` for
   2024 / 2025 / 2026 declaraciones (this exercises the new
   sibling extractor classes and the new 2026 ruleset
   registration).
8. **Mutation harness rows for 2026.** Add a `modelo_115.2026` row
   to `test_mutator_kill_rate.EXPECTED_COUNTS`. Add a 2026 entry
   to `test_percent_rate_mutation._ruleset_cases`. Add a 2026
   entry to `test_operand_swap_mutation` reusing the
   `_modelo_115_fixture` shared helper.
9. **`docs/coverage/modelos.md` row flip.** The current row reads
   `❌` on multiple Tier-L columns; flip to `✅` on every column
   this issue completes.

## Worked example template (used by `test_modelo_115_2026.py`)

The 2025 ruleset already ships
`test_external_worked_example_rirpf_100_1` as the canonical
externally-anchored case. The 2026 worked example should be a
**distinct numerical scenario** to avoid mirror-fixture coupling
(per M130 ADR §D2). Proposed scenario for 2026 (Q3, mixed
in-kind + complementaria adjustment):

- Casilla 01 (nº arrendadores): 3
- Casilla 02 (base de retención): 24 000,00 €
- Casilla 03 (retenciones, RIRPF art. 100 ¶ 1 — 19 %): 4 560,00 €
- Casilla 04 (ingresos a cuenta retribución en especie): 250,00 €
- Casilla 05 (a deducir: complementaria): 100,00 €
- Casilla 06 (resultado a ingresar): 4 560 + 250 − 100 = 4 710,00 €

Every value is independently traceable to RIRPF art. 100 and
elementary arithmetic; none is back-derived from the ruleset's
`ParameterTable`.

## Out of scope

- Overlay logic for the Ceuta / Melilla 60 % reduction (RIRPF
  art. 100 ¶ 2). Like the La Palma / Ceuta / Melilla overlays for
  M130 (per `#316` watch-list), this is caller-gated and does not
  belong in the base ruleset DAG. Defer to a dedicated future
  issue when Kent's autónomo profile demands the overlay.
- Modelo 111 (retención professional services), Modelo 180
  (annual summary of retentions). Both are separate per-modelo
  Tier-L issues (`#318`, `#323`).
- Coverage of pre-2024 years. The project ships rulesets only from
  2024 onwards per the `__init__.py` scoping rule (Modelo 130
  pre-2025 was kept for complementaria self-audit; M115 has the
  same shape via the existing 2024 ruleset).

## Cross-references

- `2026-04-27-modelo-130-calc-verify-research` — sibling
  research authored under `#321`; the M115 issue mirrors its
  structure verbatim.
- `2026-04-27-modelo-130-calc-verify-adr` — the M130 ADR is
  the procedural template for this issue's ADR.
- `2026-04-27-modelo-130-rule-delta-reference` — the M130 rule-delta manifest is the
  structural template for `2026-115-rule-delta.md`.
- EPIC `#316` — per-modelo Tier-L umbrella; this issue is its
  fourth delegation.
- Issue `#338` — mutation harness extension (consumed); the M115
  mutable surface (sub_op × 1 + percent_rate_param × 1) is fully
  exercised.
- Issue `#339` — mandatory-citation enforcement (consumed); M115
  2024 + 2025 already pass at 100 % coverage.
- Issue `#340` — Tier-L CLI integration coverage (extended); the
  `TestKentImportsModelo115Declaracion` class is already wired
  with the four mandatory cases.
