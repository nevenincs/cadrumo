---
tags:
  - '#exec'
  - '#modelo-130-calc-verify'
date: '2026-04-27'
modified: '2026-04-27'
related:
  - "[[2026-04-27-modelo-130-calc-verify-plan]]"
  - "[[2026-04-27-modelo-130-calc-verify-adr]]"
  - "[[2026-04-27-modelo-130-calc-verify-research]]"
  - "[[2026-04-27-modelo-130-rule-delta-reference]]"
---

# `modelo-130-calc-verify` phase-1 summary

Phase 1 of issue `#321` is complete on
`feature/321-modelo-130-calc-verify`. Modelo 130 reaches the Tier-L
calc-verify-roundtrip bar across 2024 / 2025 / 2026 with full
external-anchored worked examples, citation completeness, mutation-
harness coverage, 19-casilla extractor + generator round-trip, and
the optional 4th integration test classifying a deliberate
discrepancy.

## Scope landed

- **Per-year ruleset coverage.** 2024, 2025, and 2026 rulesets all
  registered in `ALL_RULESETS` with non-overlapping `effective_from /
  effective_to` windows. The 2026 ruleset is a structural and
  numerical clone of 2024 / 2025 because RIRPF art. 110 is unchanged
  across all three years (RD 253/2025 modified art. 69, not art. 110;
  consolidated text last updated 2026-02-28). Rule-delta manifest:
  `.vault/reference/2026-04-27-modelo-130-rule-delta-reference.md`.
- **Per-year extractor coverage.** `Modelo130V2024Extractor` +
  `Modelo130V2025Extractor` + `Modelo130V2026Extractor` all
  registered in the extractor registry under their respective
  `(modelo="130", año=YYYY, revision="YYYY.01")` keys. The two
  sibling classes inherit `Modelo130V2025Extractor`'s extraction
  logic verbatim and pin only their own `template_revision`
  ClassVar. (Step-4 closure of the Gemini PR-440 review finding —
  prior to step-4, only the 2025 key was registered and 2024 / 2026
  PDFs raised `NoExtractorRegisteredError`.)
- **Citation completeness.** All three M130 rulesets at 100,00 % on
  `computed=True` casillas (9 of 9). Aggregate over all 19 landed
  rulesets: 98 of 98 (100,00 %).
- **Mutation-harness coverage.** Modelo 130 2026 row added to
  `EXPECTED_COUNTS` with the same fingerprint as 2024 / 2025
  (`sub_op=8, percent_rate_param=2`). Operand-swap parametrisations
  cover all 6 `sub_op`-bearing casillas (03, 07, 11, 14, 17, 19) for
  the 2026 ruleset; percent-rate parametrisations cover both rate-
  bearing casillas (04, 09). Aggregate kill-rate floor ≥ 90 %
  preserved.
- **Worked-example coverage.** Each per-year test file ships ≥ 3
  parametrised cases per `computed=True` casilla (zero-boundary,
  typical, threshold-edge, plus an external-anchored RIRPF art. 110
  scenario). The casilla-13 minoración helper has 11 parametrised
  threshold-edge cases per year (8 boundary points + 3 floor /
  out-of-range). Every expected value externally anchored to the
  RIRPF art. 110 statute, not the ruleset's `ParameterTable`.
- **Extractor casilla-completeness.** The Modelo 130 v2025 extractor
  + the L3 synthetic generator both extended from 7 to 19 casillas
  (the full liquidación block). `_REQUIRED_FOR_COMPLETE` stays at
  the MVP-7 set so common filings preserve their `COMPLETE` verdict.
- **Round-trip closure.** `generator(params) → PDF → extractor`
  returns the same params for every casilla supplied (regression in
  `test_full_19_casilla_liquidacion_round_trip`).
  `verify_declaracion(filing, ruleset)` returns `VERIFIED` on the
  synthetic happy path; tampered fixtures produce
  `CORRECTNESS_DIVERGENCE` on the right casilla
  (`test_discrepancy_classified_correctly`).
- **Integration test class.** Three mandatory cases preserved
  (english, spanish-default, partial-extraction) plus the optional
  4th case (`test_discrepancy_classified_correctly`) plus a 5th
  parametrised case (`test_per_year_happy_path_verified`)
  exercising the full CLI flow for each of 2024 / 2025 / 2026.
- **L1 anchor decision.** Explicit waiver in the rule-delta
  manifest. AEAT does not publish a specimen Modelo 130 declaración
  as a normative exemplar.
- **Coverage docs.** `docs/coverage/modelos.md` Modelo 130 row
  flipped to reflect 2024 + 2025 + 2026 ruleset coverage and the
  19-casilla declaración-import bar; provenance line updated.

## Per-year casilla inventory

| Casilla | Mode | Statutory grounding | 2024 | 2025 | 2026 |
| :-----: | :--: | :-------------------- | :--: | :--: | :--: |
| 01 | user | RIRPF 110.1.a         | OK | OK | OK |
| 02 | user | RIRPF 110.1.a         | OK | OK | OK |
| 03 | calc | RIRPF 110.1.a         | OK | OK | OK |
| 04 | calc | RIRPF 110.1.a         | OK | OK | OK |
| 05 | user | RIRPF 110.3           | OK | OK | OK |
| 06 | user | RIRPF 110.3           | OK | OK | OK |
| 07 | calc | RIRPF 110.1.a + 110.3 | OK | OK | OK |
| 08 | user | RIRPF 110.1.c         | OK | OK | OK |
| 09 | calc | RIRPF 110.1.c         | OK | OK | OK |
| 10 | user | RIRPF 110.3           | OK | OK | OK |
| 11 | calc | RIRPF 110.1.c + 110.3 | OK | OK | OK |
| 12 | calc | RIRPF 110             | OK | OK | OK |
| 13 | user | RIRPF 110.3.c         | OK | OK | OK |
| 14 | calc | RIRPF 110.3.c         | OK | OK | OK |
| 15 | user | RIRPF 110.3           | OK | OK | OK |
| 16 | user | RIRPF 110.3.d         | OK | OK | OK |
| 17 | calc | RIRPF 110.3.c + 110.3.d | OK | OK | OK |
| 18 | user | RIRPF 110.4           | OK | OK | OK |
| 19 | calc | RIRPF 110.4           | OK | OK | OK |

## Citation audit — before / after

**Before** (origin/main, post-#339 enforcement):

```
modelo_130.2024: total=9 with_citation=9 coverage=100.00%
modelo_130.2025: total=9 with_citation=9 coverage=100.00%
```

**After** (this branch):

```
modelo_130.2024: total=9 with_citation=9 coverage=100.00%
modelo_130.2025: total=9 with_citation=9 coverage=100.00%
modelo_130.2026: total=9 with_citation=9 coverage=100.00%
aggregate (19 rulesets): total=98 with_citation=98 coverage=100.00%
```

Net delta: +9 `computed=True` casillas, +9 carrying citations, +1
ruleset registered. No `KnownBadCitation` blocklist hit.

## BOE source list

Every numerical value used in the 2024 / 2025 / 2026 rulesets is
traceable to a primary BOE source:

| Value                                   | Source                        | URL / id                                            |
| :-------------------------------------- | :---------------------------- | :-------------------------------------------------- |
| 20 % general rate                       | RIRPF art. 110.1.a            | `BOE-A-2007-6820`                                  |
| 2 % agraria rate                        | RIRPF art. 110.1.c            | `BOE-A-2007-6820`                                  |
| 9 000 / 10 000 / 11 000 / 12 000 €      | RIRPF art. 110.3.c            | `BOE-A-2007-6820` + `BOE-A-2014-12369` (RD 1003/2014) |
| 100 / 75 / 50 / 25 € minoración values  | RIRPF art. 110.3.c            | `BOE-A-2007-6820` + `BOE-A-2014-12369`             |
| 660,14 € vivienda cap                   | RIRPF art. 110.3.d            | `BOE-A-2007-6820` + `BOE-A-2013-12892` (RD 960/2013) |
| Pago a cuenta general obligation        | LIRPF art. 99                 | `BOE-A-2006-20764`                                 |
| Modelo 130 form layout                  | Orden EHA/672/2007            | `BOE-A-2007-6032`                                  |

No value was fabricated; no `notes_es="citation-pending"` casillas
were introduced; no follow-up issues filed for unverified values.

## Mutation harness — kill-rate evidence

Per `test_aggregate_kill_rate_floor_is_satisfied`: aggregate kill-
rate over the populated mutator surface remains 100 % across all
landed rulesets after the 2026 row is added. The floor is 90 % per
issue `#338` DoD; the actual rate is 100 %.

Per `test_per_ruleset_node_counts_match_expected[modelo_130.2026]`:
the mutable-node fingerprint matches the expected map verbatim.

Per `test_outer_sub_op_swap_detected`: each of the 6 `sub_op`-bearing
casillas in `modelo_130.2026` is mutated and the audit surfaces a
discrepancy on the targeted casilla with `|delta| ≥ 0.02 €`.

Per `test_percent_rate_mutation_is_detected`: each of the 2
percent-rate-bearing casillas (04, 09) in `modelo_130.2026` is
mutated by ±1 pp and the audit surfaces a discrepancy.

## Quality gates

- `just lint` (ruff + ruff-format) — green.
- `just typecheck` (ty) — green.
- `just test` — green (full suite, including the 31 new 2026 cases).
- `just hooks` (prek) — green.
- Coverage floor 60 % on `src/aeat` — preserved (the new 2026
  ruleset is mostly imports + parameter table + 9 formula-builder
  calls; every line is exercised by the new test file).

## Out of scope (per ADR § Out of scope, no drift)

- Other Tier-L modelos (`#317` M100, `#318` M111, `#319` M115,
  `#320` M123, `#322` M131, `#323` M180, `#324` M200, `#325` M202,
  `#326` M303, `#327` M390).
- Tier-S (`#328`-`#331`) and Tier-R (`#332`-`#337`) modelos.
- Sub-umbrellas `#341` (RENTA M100 deep dive), `#345` (IVA
  complexity).
- `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/sede/`, `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_clave_movil.py`,
  `src/aeat/entrypoints/cli/sede/`, `src/aeat/entrypoints/cli/sanitize/`,
  `src/aeat/entrypoints/cli/filing/_reconcile.py`,
  `src/aeat/domain/justificante/_extract.py` (#239 territory; PR #434
  landed during this issue's work and was merged in cleanly with no
  test verdict shifts).
- Error-registry / decorator infrastructure (#398, landed; consume).
- `--json` schemas / exit-code table (#399, landed; consume).
- `aeat.entrypoints.cli.audit` / `aeat.entrypoints.cli.__init__.py` (#339, landed; consume).
- Live-submit forbidden enforcement sweep (#432, held).
- Any new CLI commands or root-level Typer changes.

## Post-#239 reconciliation

PR `#434` (sibling `feature/239-aeat-verify` final cleanup) landed on
`origin/main` mid-execution. The merge was clean and re-running the
M130 integration tests + extractor unit tests post-merge surfaced
zero verdict shifts. No fixture or assertion update needed.

## Closure trail

- Research: `.vault/research/2026-04-27-modelo-130-calc-verify-research.md`
- ADR: `.vault/adr/2026-04-27-modelo-130-calc-verify-adr.md`
- Plan: `.vault/plan/2026-04-27-modelo-130-calc-verify-plan.md`
- Reference: `.vault/reference/2026-04-27-modelo-130-rule-delta-reference.md`
- Exec records: `.vault/exec/2026-04-27-modelo-130-calc-verify/...`
- Coverage docs: `docs/coverage/modelos.md` Modelo 130 row flipped.
- Parent EPIC: `#316`.
- Issue: `#321` (this issue).
