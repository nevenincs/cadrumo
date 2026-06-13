---
tags:
  - '#adr'
  - '#modelo-390-calc-verify'
date: '2026-04-27'
modified: '2026-04-27'
related:
  - "[[2026-04-27-modelo-390-calc-verify-research]]"
  - "[[2026-04-27-modelo-303-calc-verify-adr]]"
  - "[[2026-04-27-modelo-130-calc-verify-adr]]"
  - "[[2026-04-25-mandatory-citations-adr]]"
---

# `modelo-390-calc-verify` adr: tier-l calc-verify-roundtrip for the annual iva resumen | (**status:** `accepted`)

## Problem Statement

EPIC `#316` requires per-modelo Tier-L calc-verify-roundtrip coverage for Modelo 390 across 2024, 2025, and 2026. The repository currently ships only a 2025 Modelo 390 ruleset (an MVP with three computed casillas: `104`, `105`, `190`) plus a 2025 declaración extractor that pulls 15 casillas. There is no 2024 ruleset, no 2026 ruleset, no rule-delta manifest, no L1 anchor decision, no result-block computation chain (`191` / `192` / `193`), and no cumulation evidence tying the annual M390 to its four quarterly Modelo 303 sources. The existing 2025 ruleset also embeds wave-numbered comments that violate the project's no-wave/phase-numbering source-code discipline and lacks LIVA citations on the rate-anchored computations.

## Considerations

The Modelo 130 (`#321`), Modelo 115 (`#319`), Modelo 111 (`#318`), Modelo 123 (`#320`), Modelo 131 (`#322`), and Modelo 303 (`#326`) implementations have established the canonical Tier-L pattern: per-year ruleset modules with year-stamped formula identifiers, BOE-cited rule-delta documentation, mutation-harness fingerprint enumeration, citation-coverage audit, L1 anchor decision, and Kent CLI integration coverage.

Modelo 390 differs from those impls along two axes:

- Annual aggregator. The form summarises four quarterly Modelo 303 filings plus the annual prorrata regularización and bienes-de-inversión regularización. The cumulation pattern is one of the surfaces issue `#437` (needs-design ADR for aggregator cumulation) is open to formalise once enough cases have surfaced. `#437` has not landed.
- Result-block depth. The MVP only covers `104`, `105`, and `190`. The actual M390 form has `191` (cuota resultante anual after bienes-inversión), `192` (a ingresar — positive part), `193` (a devolver — sign-flipped negative part), and `662` (regularización bienes inversión input). Tier-L correctness requires the full result chain.

The research note `[[2026-04-27-modelo-390-calc-verify-research]]` evaluates three cumulation approaches (DSL aggregator primitive, live-AEAT-driven, user-supplied annual aggregates) and concludes that approach C — user-supplied — is the right pick. It mirrors Modelo 180's pattern (annual IRPF retention summary), avoids inventing a DSL primitive that `#437` may later prescribe differently, and still allows cumulation-correctness assertions at the test level.

Primary BOE evidence — verified via the BOE consolidated text and the existing `#326` Modelo 303 research — confirms no scoped algebraic change between 2024, 2025, and 2026 for the casillas this ruleset encodes:

| Reference | Role | BOE id |
| :--- | :--- | :--- |
| LIVA art. 90 | 21 percent general IVA rate | `BOE-A-1992-28740#a90` |
| LIVA art. 91 | 10 percent reduced and 4 percent super-reduced rates | `BOE-A-1992-28740#a91` |
| LIVA arts. 92-100 | IVA soportado deducible framework | `BOE-A-1992-28740` |
| LIVA arts. 102-106 | Prorrata reglas | `BOE-A-1992-28740` |
| LIVA arts. 107-110 | Regularización por bienes de inversión | `BOE-A-1992-28740` |
| LIVA art. 164 | Self-assessment + resumen-anual obligation | `BOE-A-1992-28740` |
| RIVA art. 71 | IVA liquidation period and Modelo 390 obligation | `BOE-A-1992-28925` |
| Orden EHA/3111/2009 | Approval of Modelo 390 form | `BOE-A-2009-18472` |
| Directiva (UE) 2020/285 | 2026 small-enterprise franquicia regime — out of scope here | `DOUE-L-2020-80356` |

The 2026 franquicia IVA mandate creates an *opt-in regime* under which a participating taxpayer drops out of the standard Modelo 390 surface entirely. It is not a modification of the régimen-general result chain that this ruleset encodes; it belongs to sub-EPIC `#345` IVA complexity.

## Constraints

- The implementation must not expand into `#345` IVA complexity children. Per-rate-bucket Apartado 3 detail, deeper prorrata derivation, deeper bienes-de-inversión regularisation, OSS / IOSS, foral / regional regimes, and 2026 franquicia full hardening are all out of scope.
- Every computed casilla must carry a non-empty `LegalCitation` per issue `#339`. The 2025 ruleset's existing two citations (RIVA art. 71.7 and Orden EHA/3111/2009) are correct for the *obligation to file*, but the rate-anchored computed casillas (`104`, `105`) need LIVA arts. 90 / 91 / 92-100 anchored citations as well.
- Tests must use real rulesets, real formula engine evaluations, real synthetic PDFs, and real CLI invocations. No mocks, fakes, stubs, or skips.
- No live AEAT submission paths are involved. Live AEAT submission is permanently forbidden under the project's safety charter.
- The 2025 ruleset's wave-numbered comments must be removed; the project mandates no wave / phase numbering in source code or docstrings.
- The integration class `TestKentImportsModelo390Declaracion` in `tests/integration/test_kent_workflows.py` already ships three mandatory cases (English happy, Spanish happy, partial extraction) plus a fourth discrepancy-classifier case. The implementation must keep all four passing as the casilla surface expands.

## Implementation

### Per-year ruleset structure

The 2024 ruleset becomes the master: it owns the casilla tuple `_CASILLAS`, the citation tuple `_CITATIONS`, and the formula tuple `_FORMULAS_2024`. The 2025 and 2026 rulesets re-import `_CASILLAS` and `_CITATIONS` from 2024, redeclare year-scoped formulas and a year-bound `ParameterTable` (empty by design — Modelo 390 has no DSL parameters in scope; every rate lives in the upstream Modelo 303 quarterly ruleset), and bind to their own effective-from / effective-to range.

This pattern matches the landed Modelo 303 layout (`modelo_303_2024.py` master, `modelo_303_2025.py` and `modelo_303_2026.py` re-importing). Subsequent divergence (e.g., a future scoped algebraic change) lands cleanly in a single year-specific module.

### Casilla surface (15 casillas)

Aligned to the extractor's parsed casilla set:

| Casilla | computed | Role |
| :--- | :--- | :--- |
| `01`, `04` | no | Apartado 1 — datos estadísticos Q1 base / cuota |
| `95` | no | Total bases imponibles (annual aggregate of quarterly bases) |
| `96` | no | Total cuotas repercutidas (annual aggregate of quarterly cuotas) |
| `100`, `101` | no | Total IVA soportado deducible interior / importaciones |
| `104` | yes | Total IVA soportado deducible (= 100 + 101) |
| `105` | yes | Resultado régimen general (= 96 - 104) |
| `108`, `109` | no | Resultado simplificado / otros regímenes |
| `190` | yes | Suma resultado (= 105 + 108 + 109) |
| `191` | yes | Cuota resultante anual (= 190 - 662) |
| `192` | yes | Total a ingresar (= clamp_pos(191)) |
| `193` | yes | Total a devolver (= clamp_pos(0 - 191)) |
| `662` | no | Regularización bienes de inversión (annual user-supplied adjustment) |

The pair `192` / `193` is mutually exclusive at any point: when `191 ≥ 0` then `192 = 191` and `193 = 0`; when `191 < 0` then `192 = 0` and `193 = -191`. Independent `clamp_pos` chains preserve this invariant without branching.

### Cumulation strategy (Approach C)

The cumulated casillas (`95`, `96`, `100`, `101`, `108`, `109`, `662`) stay user-supplied. The ruleset only encodes the algebraic relationships among them. Cumulation correctness is asserted at the test level: a dedicated test class generates four synthetic Modelo 303 quarterly fixtures with chosen rate-bucket inputs, computes the expected annual sums (per-rate sum of `09 + 06 + 03` for casilla 96, per-rate sum of taxable bases for casilla 95, etc.), generates a Modelo 390 fixture with those sums, and verifies the round-trip closes.

This approach matches the landed Modelo 180 pattern (annual IRPF retention summary). It defers the question of how a DSL aggregator primitive should look to issue `#437` once more cumulation cases (M390, M180, M190, M193, M347, M349) have informed the design.

### Citation completeness

The 2024 ruleset master declares LIVA arts. 90, 91, 92, 102, 107, 164 plus RIVA art. 71.7 plus Orden EHA/3111/2009 in `_CITATIONS`. Each computed casilla is bound to the citations that ground its computation:

- `104` ← LIVA arts. 92, 102 (deducción + prorrata)
- `105` ← LIVA arts. 90, 91 (rate buckets), 164 (autoliquidación)
- `190` ← LIVA art. 164 (autoliquidación)
- `191` ← LIVA arts. 107-110 (regularización bienes de inversión), 164
- `192`, `193` ← LIVA art. 164 (resultado a ingresar / a devolver)

The CLI command `aeat audit rulesets citations` reports 100 percent coverage on Modelo 390 after the back-fill.

### Extractor

The existing `Modelo390V2025Extractor` already pulls all 15 casillas the new ruleset declares. Two thin sibling subclasses are added: `Modelo390V2024Extractor` (template_revision `2024.01`, año 2024) and `Modelo390V2026Extractor` (template_revision `2026.01`, año 2026). Both inherit the same line-anchored regex map.

### Synthetic generator

The existing `_generic_quarterly_generator` already handles the M390 layout via `QuarterlyGenParams` with `period_printed="0A"`. The Kent integration test calls it through `_synth_annual_pdf`. No generator changes needed.

### L1 anchor decision

Modelo 390 declarations are taxpayer-specific and contain private NIF / period / liquidation data. The same waiver pattern as Modelo 303 (`#326`) applies: an explicit waiver lives at `.vault/reference/2026-04-27-modelo-390-l1-anchor-waiver-reference.md`, and L3 synthetic PDFs remain the executable evidence tier. The waiver is revisited if AEAT publishes a non-private completed Modelo 390 declaration exemplar.

### Mutation-harness extension

The fingerprint becomes:

| Surface | 2024 / 2025 / 2026 |
| :--- | :--- |
| `sub_op` | 3 (casilla 105 + casilla 191 + casilla 193 internal) |
| `clamp_pos` | 2 (casilla 192 + casilla 193) |
| `add_op` | 2 (casilla 104 + casilla 190) |
| `percent_rate_*` | 0 |
| `mul_div_scalar` | 0 |
| `brackets_threshold_non_terminal` | 0 |

`EXPECTED_COUNTS` in `test_mutator_kill_rate.py` is updated for the three years. Operand-swap mutation tests gain a 2026 case for casilla 105 mirroring the existing 2025 case; the 105 chain is the same across the three years so a single representative case per year suffices.

### Integration test

The integration class `TestKentImportsModelo390Declaracion` keeps all four cases. The English / Spanish happy-path values in `_M390_HAPPY` already round-trip cleanly with the extended ruleset (104 = 100+101, 105 = 96-104, 190 = 105+108+109, 191 = 190-662, 192 = clamp_pos(191), 193 = clamp_pos(-191)). The partial-extraction case keeps its `casilla 190` / `casilla 192` assertion (warnings carry these casilla mentions). The discrepancy-classifier case keeps its casilla-190 drift assertion.

### Reference manifest

`.vault/reference/2026-04-27-modelo-390-rule-delta-reference.md` documents the per-year sameness with BOE citations and the cumulation rules section: which quarterly Modelo 303 casillas feed which annual Modelo 390 casillas.

## Rationale

A clone-with-year-scoped-IDs is safer than encoding speculative future regime behaviour. The current ruleset only represents the régimen-general result chain Kent's autónomo profile produces; the underlying BOE text is stable, and inventing scope expansion inside this issue would either preempt `#345` IVA complexity sub-EPIC or tangle with `#437` aggregator-primitive design.

Approach C cumulation matches the existing Modelo 180 pattern and keeps the surface thin enough that a future `#437`-prescribed primitive can replace the user-supplied annual aggregates transparently in a follow-up refactor.

The L1 waiver reuses the same justification as Modelo 303: real declaraciones are private, public legal anchors stay in BOE citations, executable evidence stays in L3 synthetic round-trip plus Kent CLI integration.

The 8-citation backfill on the 2025 ruleset closes the issue `#339` mandatory-citation invariant for Modelo 390 without inventing new citations: every computed casilla is grounded in a LIVA / RIVA / Orden Ministerial article that already grounds another modelo in this codebase.

## Consequences

- Modelo 390 resolves and verifies for 2024, 2025, and 2026 with 100 percent citation coverage on computed casillas and mutation-harness enumeration for the new 2026 nodes.
- The result chain doubles in depth (3 → 6 computed casillas) so the existing 2025 worked-example tests need expansion to cover `191`, `192`, `193` plus the regularización bienes-inversión cases. The expansion lands inside the per-year test files.
- The integration partial-extraction assertion remains satisfied because the warnings list is unchanged in shape (any unfound casilla still surfaces a `casilla N` mention).
- Expected ruleset shape `{"104", "105", "190"}` in the existing `test_ruleset_shape` becomes `{"104", "105", "190", "191", "192", "193"}` and `len(formulas) == 6`. The expanded shape is updated in-place in the 2025 test file.
- Operand-swap mutation tests gain three sub_op chains per year (105, 191, 193 internal). Aggregate kill-rate floor of 90 percent stays satisfied.
- The 2026 franquicia IVA mandate is acknowledged in the rule-delta manifest as a watch-list item but explicitly out of scope. Subsequent IVA complexity work under `#345` will revisit it.
- The cumulation test class produces 4 synthetic quarterly Modelo 303 PDFs plus 1 annual Modelo 390 PDF per parametrised case. Test runtime stays within the existing per-class budget because PDF generation is sub-second.
- Issue `#437` may later prescribe a different cumulation pattern for annual aggregators. If so, this implementation provides a known-good test-level baseline; the refactor harmonises the test-level assertion with the prescribed DSL primitive without disturbing the M390 ruleset's user-facing API.
