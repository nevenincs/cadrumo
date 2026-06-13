---
tags:
  - '#adr'
  - '#modelo-130-calc-verify'
date: '2026-04-27'
modified: '2026-04-27'
related:
  - "[[2026-04-27-modelo-130-calc-verify-research]]"
  - "[[2026-04-25-mandatory-citations-adr]]"
  - "[[2026-04-25-mutation-harness-extension-adr]]"
---

# `modelo-130-calc-verify` ADR — child of EPIC `#316` | (**status:** `accepted`)

## Status note (2026-05-21)

Accepted — status field resolved during the branch-reconciliation
campaign. The Modelo 130 calc-verify decision is implemented and
verified: casilla `03 = 01 − 02` (rendimiento neto) is a registry
formula (`modelo-130-rendimiento-neto`) and is gated by the
`modelo-130-calculation-verification` `verification_expectations`
stanza. The ADR's references to a post-PR-440 declaración extractor
registry predate the registry-driven declaración re-architecture; that
infrastructure detail is superseded but does not affect the accepted
calc-verify decision.

## Context

EPIC `#316` is the per-modelo Tier-L calc-verify-roundtrip umbrella;
issue `#321` is the first delegation under that umbrella. The three
foundational chores it depends on (`#338` mutation harness extension,
`#339` mandatory `LegalCitation` enforcement, `#340` Tier-L CLI
integration coverage) are landed on `main`.

The audit referenced in EPIC `#316` (2026-04-22 calc-verify-roundtrip
audit) flagged Modelo 130 as the **reference implementation** of the
calc-verify universe: every per-modelo issue that follows (#317 M100,
#318 M111, #319 M115, #320 M123, #322 M131, #323 M180, #324 M200,
#325 M202, #326 M303, #327 M390) will mirror the patterns set here.
The quality bar is therefore deliberately high.

The research document
(`2026-04-27-modelo-130-calc-verify-research`) confirms three load-
bearing facts:

1. The 2024 → 2025 → 2026 rule delta on RIRPF art. 110 is **zero** —
   no 2025 or 2026 BOE amendment touches the 110-series numerical
   surface. The 2026 ruleset is a structural clone of 2025 with new
   effective-date boundaries.
2. The existing 2024 + 2025 rulesets already pass `#339`'s mandatory-
   citation validator (every `computed=True` casilla on these rulesets
   has a non-empty `legal_basis` pointing at RIRPF art. 110 and
   LIRPF art. 99). No back-fill is required for citation coverage; an
   audit pass confirms the existing surface.
3. The existing harness coverage (`#338`) already exercises Modelo 130
   2024 + 2025 at `sub_op=8, percent_rate_param=2`. The 2026 ruleset
   inherits the same fingerprint and the harness tables need a single
   row per case.

The current per-issue gaps are:

- **No 2026 ruleset** registered.
- **No `2026-04-27-modelo-130-rule-delta-reference.md`** documenting the 2024 → 2025 → 2026
  delta with BOE citations.
- **No L1 anchor decision** for Modelo 130.
- **Threshold-edge worked examples** for the casilla-13 minoración
  brackets are missing from the per-year test files.
- **Synthetic generator + extractor** ship at MVP coverage (7 of 19
  casillas) — Tier-L bar calls for casilla-completeness across the
  printed liquidación block.
- **Optional fourth integration case** (`test_discrepancy_classified_correctly`)
  is not wired.

## Decision

### D1. 2026 ruleset is a structural clone of 2025

Author `src/aeat/domain/formulas/_rulesets/modelo_130_2026.py` as a clone of
the 2025 module: it imports `_CASILLAS_2024` + `_CITATIONS_2024` from
`modelo_130_2024`, declares its own `_FORMULAS_2026` with the
`modelo_130.2026.<reason>` formula-id namespace, and ships its own
`ParameterTable` with `effective_from=2026-01-01` /
`effective_to=2026-12-31`. The numerical content of the
`ParameterTable` is identical to 2024 / 2025: `irpf.trimestral_rate =
0.20`, `agraria.trimestral_rate = 0.02`. This mirrors the existing
2024 → 2025 clone pattern.

Register `MODELO_130_2026` in `src/aeat/domain/formulas/_rulesets/__init__.py`
and add it to `ALL_RULESETS`.

**Why a clone, not a re-import.** The existing 2025 ruleset re-imports
`_CASILLAS` + `_CITATIONS` from 2024 but **declares its own
`_FORMULAS`** so the formula-id namespace remains year-scoped (e.g.
`modelo_130.2025.rendimiento_neto`). This namespacing matters: the
formula-id is the stable handle the engine uses for ledger entries
and audit reports. The 2026 ruleset follows the same pattern with
`modelo_130.2026.<reason>`.

### D2. External-anchor strategy — mirror `test_external_worked_example_rirpf_art_110`

Every per-year test file ships at least one
`test_external_worked_example_rirpf_art_110_<year>` case whose
expected values are computed *from the statute* (RIRPF art. 110.1.a /
art. 110.1.c) rather than from the ruleset's `ParameterTable`. A
mis-stored rate in any year's `ParameterTable` would therefore fail
the test.

For 2024 + 2025 the existing files already carry such tests; the only
extension is **threshold-edge cases for the casilla-13 minoración**
(boundary tests at 8 999,99 / 9 000,01 / 10 000,00 / 10 000,01 /
11 000,00 / 11 000,01 / 12 000,00 / 12 000,01 €). These exercise the
minoración helper `compute_casilla_13_minoracion` against the bracket
boundaries directly defined in RIRPF art. 110.3.c.

For 2026 the worked example is a **distinct numerical scenario** from
2024 / 2025 to avoid mirror-fixture coupling: a Q3 2026 mixed-régimen
autónomo with both an Apartado I slice (estimación directa) and an
Apartado II slice (agraria) plus a non-zero minoración.

### D3. Casilla-13 minoración helper — eight threshold-edge cases

The casilla-13 minoración is the single non-trivial brackets surface
on Modelo 130. The bracket boundaries (9 000 / 10 000 / 11 000 /
12 000 €) are statutory thresholds in RIRPF art. 110.3.c. Each per-
year test file gains a parametrised
`test_casilla_13_minoracion_brackets` case enumerating the eight
boundary points (one ε below + one ε above each of the four
boundaries) plus zero-boundary (`previous_year_rendimiento_neto =
0,00`) and out-of-range (`12 500,00 € → 0 €`).

These are *external-anchored* — the expected bracket values are taken
from RIRPF art. 110.3.c verbatim, not derived from
`_CASILLA_13_BRACKETS`. A typo in the bracket boundary inside the
ruleset would therefore fail this test.

### D4. Per-year ruleset test marker

The existing M130 ruleset tests use `pytest.mark.unit,
pytest.mark.domain_local_state` (line 18 of
`test_modelo_130_2024.py`; line 19 of `test_modelo_130_2025.py`). The
issue body calls for `pytest.mark.domain_submission`. The repo-wide
convention for *ruleset* tests is `domain_local_state` (the formula
DSL is a local-state surface — the rulesets ship as data, with no
AEAT-write / submission-boundary semantics). `domain_submission` is
applied to harness tests that exercise the *aggregate* mutation
surface across rulesets (`test_percent_rate_mutation`,
`test_brackets_threshold_mutation`, `test_mutator_kill_rate`,
`test_scalar_mutation`).

**Decision.** Align the new `test_modelo_130_2026.py` with the
existing per-ruleset convention (`domain_local_state`) so the
rulesets directory stays internally consistent. Diverging on a single
year would introduce drift the kill-rate harness already disallows.
The issue body's instruction predates the wave-distinct marker
specialisation; the project mandate (CLAUDE.md §Testing) defers to
the existing pyproject marker definitions, which read:

- `domain_local_state`: "exercises on-disk catalogues and local
  SQLite mirror (storage, models, normatives, manuals, corpus,
  schema, deadlines, cli/deadlines)" — applies to formula rulesets,
  which are local-state data.
- `domain_submission`: "exercises the AEAT-write-capable submission
  boundary (filing, submission)" — does not apply to a per-ruleset
  test that audits the engine against a fixed fixture.

The 2024 / 2025 back-fills also keep their existing
`domain_local_state` markers; an across-the-board switch is out of
scope for this issue.

### D5. Synthetic generator + extractor — extend to all 19 casillas, keep `_REQUIRED_FOR_COMPLETE` at the 7-MVP set

Extend `tests/fixtures/pdf_corpus/l3_synthetic/_generators/modelo_130_generator.py`
to render all 19 casilla boxes (the 7 existing + 12 new positions on
the same A4 page). Extend
`src/aeat/adapters/inbound/declaracion/_extractors/modelo_130_v2025.py` to add label
regexes for the same 12 casillas; the regex shape mirrors the
existing 7 (`label-anchored Spanish-amount-group`).

**`_REQUIRED_FOR_COMPLETE` stays at the existing 7-casilla set.** The
existing 7 (01 – 07) are what the *Tier-L* bar treats as the
must-extract MVP — they appear on every Modelo 130 declaración with
non-zero values for any non-trivial filing. The remaining 12
(08 – 19) are *liquidación-completion* casillas that may print
`0,00 €` for many real filings (e.g. an autónomo with no agraria
income carries 08 – 11 = 0 by construction). Treating them as
must-extract would surface false-negative `casilla-not-found`
warnings for those zero-value rows.

The PDF round-trip invariant remains: `generator(params) → PDF →
extractor` returns the same `params` for every casilla supplied to
the generator. The extractor *can* parse all 19; the *required* set
is 7. This is the same scoping the existing extractor uses for
`_REQUIRED_FOR_COMPLETE` vs `_MODELO_130_CASILLAS`.

### D6. Round-trip strategy

Per the `aeat.domain.formulas` engine's `audit_against` contract, a
verification pass returns `VERIFIED` when:

- Every `computed=True` casilla supplied to `provided` matches the
  engine's re-derivation within the supplied tolerance (default
  `0.01 €`).
- No discrepancies surface on `computed=True` casillas the user
  supplied.

The synthetic-generator → extractor → `verify_declaracion(filing,
ruleset)` round-trip closes when the generator emits a clean PDF, the
extractor returns `ExtractionStatus.COMPLETE`, and the verification
returns `VERIFIED`. The integration tests in
`TestKentImportsModelo130Declaracion` already exercise this for 2025
via `aeat filing import --from-declaracion`.

### D7. Optional 4th integration test — wire it

The optional `test_discrepancy_classified_correctly` is the issue's
stretch goal. Modelo 130 is the reference implementation of
`verify_declaracion`'s `ClassifiedDiscrepancy` taxonomy: extraction /
formula / un-modelled / rounding. Wiring this case is a low-risk
addition that exercises the classifier on its primary surface.

**Plan.** Generate a PDF where casilla 04 prints a value
deliberately disagreeing with `20 % · 03` (e.g., 03 = 10 000,00 →
04 = 1 800,00 instead of 2 000,00 — a 200,00 € drift). The
verification pass should classify the discrepancy as a
`FORMULA_DIVERGENCE` (the printed value disagrees with the engine's
re-derivation; both inputs were extracted reliably). Assert on a
stable marker substring, not the full envelope, so future error-text
evolution does not break the test. Spanish-default + explicit-English
both covered.

The marker depends on the existing classifier output. The current
`aeat filing import --from-declaracion` CLI already prints a
classified discrepancy for the same input shape via the
verification renderer. Asserting on the substring
`Verification status: NEEDS_REVIEW` plus a casilla-04 reference
keeps the test forward-compatible.

### D8. Rule-delta manifest + L1 waiver

Author `.vault/reference/2026-04-27-modelo-130-rule-delta-reference.md` with the structure:

- **Per-year delta table.** Three rows (2024, 2025, 2026) listing
  the rate / threshold / deduction values and the BOE citation that
  grounds each.
- **Diff narrative.** "2024 → 2025: no amendment. 2025 → 2026: no
  amendment." with the BOE-A reference and consolidated-text last-
  update date that supports each statement.
- **L1 waiver.** A dedicated section explaining why no real public
  Modelo 130 declaración PDF is hash-pinned: AEAT does not publish
  any specimen Modelo 130 declaración as a normative exemplar
  because every real filing is a private autoliquidación of a
  specific NIF/quarter. The Manual práctico de IRPF prints worked
  numerical examples of art. 110 but those are not the printed PDF
  declaración itself.

Tag the file `#reference, #modelo-130-calc-verify`. Wiki-link it
from the `2026-04-27-modelo-130-calc-verify-research` and `2026-04-27-modelo-130-calc-verify-adr` documents.

### D9. Cent-exact rounding policy

The terminal `RoundFormula(digits=2, ROUND_HALF_UP)` ships in the
`formula(...)` helper — every `FormulaDefinition` is wrapped in this
terminal round at construction time. This is the project-wide single-
rounding invariant and the 2024 + 2025 rulesets already conform; the
2026 ruleset inherits the same wrapping by construction.

Boundary tests at the 0,01 € detection floor are already part of the
mutation harness (`#338` detection floor is `|delta| ≥ 0.02 €` per
mutated case). The per-year test files extend this with explicit
threshold-edge cases at 0,01 € above / below the casilla-13 bracket
boundaries.

### D10. Mutation-harness coverage tables

Three harness files require a single new row each per the 2026
ruleset's structural fingerprint:

- `test_mutator_kill_rate.py::EXPECTED_COUNTS` — add
  `"modelo_130.2026": {sub_op: 8, percent_rate_literal: 0,
   percent_rate_param: 2, percent_rate_compound_skipped: 0,
   percent_rate_casilla_ref_skipped: 0,
   brackets_threshold_non_terminal: 0, mul_div_scalar: 0}`.
- `test_operand_swap_mutation.py::test_outer_sub_op_swap_detected` —
  add 6 × `pytest.param` entries for casillas 03, 07, 11, 14, 17, 19
  pointed at `MODELO_130_2026` reusing the existing
  `_modelo_130_rich_fixture`.
- `test_percent_rate_mutation.py::_ruleset_cases` — add 2 ×
  `(MODELO_130_2026, "04", _f130_irpf_fixture())` and
  `(MODELO_130_2026, "09", _f130_agraria_fixture())`.

The fixtures are reused unchanged because the 2026 ruleset is
structurally identical to 2024 / 2025.

### D11. Coverage docs flip

`docs/coverage/modelos.md` carries one row per modelo. Flip the
M130 row to ✅ on the columns this issue completes (per-annum-coverage
2024/2025/2026, calc-verify, integration-test, citation-coverage,
mutation-coverage). Add a provenance line citing this PR
(`Closes #321`).

## Consequences

### Positive

- Modelo 130 reaches the Tier-L bar on calc-verify-roundtrip across
  2024 / 2025 / 2026.
- The reference implementation is documented exhaustively for the
  ten remaining per-modelo Tier-L issues to mirror.
- The rule-delta manifest pattern is established (a per-modelo
  reference file the audit + ADR + plan all wiki-link to).
- The L1 waiver pattern is established for modelos AEAT does not
  publish as normative exemplars — applies symmetrically to most
  per-form Tier-L modelos.
- Synthetic generator + extractor coverage moves from MVP-7 to
  full-19 without breaking the existing `COMPLETE`-on-7
  back-compat.

### Negative / risks

- **Extractor regex map widens** — 12 new label regexes increase the
  surface that has to be regression-tested. Mitigation: the existing
  `test_modelo_130_v2025_extractor` (or its colocated test file)
  already exercises the per-casilla regex; extending its
  parametrisation to 19 casillas keeps the surface covered. (If no
  such co-located test exists, this issue ships one.)
- **Synthetic generator widens** — 12 new `CasillaBox` positions on
  the A4 page need to fit the existing layout. The current 7 boxes
  occupy y_mm = 60 – 125; the extension uses y_mm = 135 – 245 for the
  remaining 12 boxes (10 mm vertical pitch). The page is A4 so
  297 mm tall; y_mm = 245 leaves clearance for the footer.
- **Integration test 4th case** is the highest-friction addition —
  if the discrepancy classifier surface evolves (e.g., wave-71
  envelope rework, post-#398 error registry), the assertion has to
  be re-checked. Mitigation: assert on stable substrings only.

### Out of scope

Per STEP 5 of the handover prompt:

- Other Tier-L modelos (#317 M100, #318 M111, #319 M115, #320 M123,
  #322 M131, #323 M180, #324 M200, #325 M202, #326 M303, #327 M390).
- Tier-S (#328-#331) and Tier-R (#332-#337).
- Sub-umbrellas #341 (RENTA M100), #345 (IVA complexity).
- `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/sede/`, `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_clave_movil.py`,
  `src/aeat/entrypoints/cli/sede/`, `src/aeat/entrypoints/cli/sanitize/`,
  `src/aeat/entrypoints/cli/filing/_reconcile.py`,
  `src/aeat/domain/justificante/_extract.py` (#239 territory).
- Error-registry / decorator infrastructure (#398, landed; consume).
- `--json` output schemas / exit-code table (#399, landed; consume).
- `aeat.entrypoints.cli.audit` / `aeat.entrypoints.cli.__init__.py` (#339, landed; consume).
- Live-submit forbidden enforcement sweep (#432, held).
- Any new CLI commands or root-level Typer changes.

## References

- `2026-04-27-modelo-130-calc-verify-research` — research findings.
- `2026-04-25-mandatory-citations-adr` — `#339` mandatory-citation
  enforcement (consumed here).
- `2026-04-25-mutation-harness-extension-adr` — `#338` mutation
  harness extension (consumed here).
- `2026-04-25-kent-workflows-expansion-adr` — `#340` Tier-L CLI
  integration coverage (extended here).
- EPIC `#316` — per-modelo calc-verify-roundtrip umbrella.
- Issue `#321` — this issue.
- RD 439/2007 art. 110 — `BOE-A-2007-6820`.
- LIRPF art. 99 — `BOE-A-2006-20764`.
- Orden EHA/672/2007 — `BOE-A-2007-6032`.
