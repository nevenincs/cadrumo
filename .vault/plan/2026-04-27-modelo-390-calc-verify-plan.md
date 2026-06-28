---
tags:
  - '#plan'
  - '#modelo-390-calc-verify'
date: '2026-04-27'
modified: '2026-04-27'
related:
  - "[[2026-04-27-modelo-390-calc-verify-research]]"
  - "[[2026-04-27-modelo-390-calc-verify-adr]]"
  - "[[2026-04-27-modelo-303-calc-verify-adr]]"
  - "[[2026-04-27-modelo-130-calc-verify-adr]]"
---

# `modelo-390-calc-verify` plan

Tier-L calc-verify-roundtrip implementation for Modelo 390 (annual IVA resumen) across 2024 / 2025 / 2026, closing issue `#327` under EPIC `#316`.

## Proposed Changes

Per the ADR `[[2026-04-27-modelo-390-calc-verify-adr]]`, ship a structurally cloned per-year ruleset trio for Modelo 390 with year-stamped formula identifiers, expand the existing 2025 ruleset's casilla surface from 8 to 15 casillas (matching the extractor) and the formula chain from 3 to 6 computed casillas (`104` / `105` / `190` / `191` / `192` / `193`), back-fill citation gaps to satisfy the `#339` mandatory-citation invariant, register sibling 2024 / 2026 declaración extractors, document the per-year sameness in `.vault/reference/`, ship an L1 anchor waiver, extend the mutation-harness fingerprint, add cumulation tests asserting that Σ four quarterly Modelo 303 fixtures equals one annual Modelo 390 fixture, and keep the existing four Kent CLI integration cases passing.

## Tasks

- Phase 1 — Vault docs (already produced before implementation begins)
  1. Research note authored — `[[2026-04-27-modelo-390-calc-verify-research]]`
  1. ADR authored — `[[2026-04-27-modelo-390-calc-verify-adr]]`
  1. Plan authored — this document

- Phase 2 — Refactor existing 2025 ruleset to the year-master pattern
  1. Promote `modelo_390_2025.py` casillas + citations into a new `modelo_390_2024.py` master module
  1. Strip wave-numbered comments + back-fill LIVA arts. 90 / 91 / 92 / 102 / 107 / 164 citations
  1. Re-author `modelo_390_2025.py` to import `_CASILLAS` and `_CITATIONS` from 2024, declare year-scoped `_FORMULAS_2025`, bind to 2025 effective range
  1. Author `modelo_390_2026.py` mirroring 2025 with 2026 effective range and `modelo_390.2026.*` formula IDs
  1. Register `MODELO_390_2024` and `MODELO_390_2026` in `_rulesets/__init__.py`

- Phase 3 — Casilla + formula surface expansion (15 casillas, 6 computed)
  1. Add user-supplied casilla rows: `01`, `04`, `95`, `662` (extractor surface compatibility)
  1. Add computed casilla rows: `191` (= 190 - 662), `192` (= clamp_pos(191)), `193` (= clamp_pos(0 - 191))
  1. Bind LIVA arts. 107-110 citation to `191`, LIVA art. 164 to `192` and `193`
  1. Update existing computed casillas `104`, `105`, `190` with appropriate LIVA citations

- Phase 4 — Declaración extractor sibling registration
  1. Add `Modelo390V2024Extractor` (template_revision `2024.01`) and `Modelo390V2026Extractor` (template_revision `2026.01`) as thin subclasses of `Modelo390V2025Extractor`
  1. Register both in `declaracion/_extractors/__init__.py`

- Phase 5 — Mutation-harness extension + per-class operand-swap coverage
  1. Update `EXPECTED_COUNTS` for `modelo_390.2024`, `modelo_390.2025`, `modelo_390.2026` (sub_op = 3, add_op = 2, clamp_pos = 2 — verified via the existing fingerprint walker)
  1. Extend `test_operand_swap_mutation.py` with the additional sub_op chains (`191`, `193` internal) for 2025; add 2024 / 2026 cases for casilla `105`

- Phase 6 — Per-year worked-example tests
  1. Author `test_modelo_390_2024.py` with ≥ 3 parametrised cases (zero-boundary, typical, threshold-edge)
  1. Refactor `test_modelo_390_2025.py` shape assertion to `{"104", "105", "190", "191", "192", "193"}` and `len(formulas) == 6`; add 191 / 192 / 193 worked-example cases
  1. Author `test_modelo_390_2026.py` mirroring 2025
  1. Anchor every expected value to a BOE article

- Phase 7 — Cumulation test (Approach C)
  1. New parametrised test class generates four synthetic Modelo 303 quarterly PDFs (1T, 2T, 3T, 4T), computes per-rate-bucket sums, generates an annual Modelo 390 PDF with those sums, runs the M390 extractor, audits against the M390 ruleset, asserts cleanness
  1. Cumulation-edge case: one quarter with negative `45` / large compensación, annual `662` regularización flips `191` from positive to negative

- Phase 8 — Reference manifest + L1 anchor waiver
  1. Author `.vault/reference/2026-04-27-modelo-390-rule-delta-reference.md` per-year diff with BOE citations + cumulation rules section
  1. Author `.vault/reference/2026-04-27-modelo-390-l1-anchor-waiver-reference.md` mirroring the Modelo 303 waiver

- Phase 9 — Integration test verification
  1. Confirm `TestKentImportsModelo390Declaracion` cases (English / Spanish / partial / discrepancy) still pass with the expanded ruleset
  1. Adjust the `_M390_HAPPY` fixture only if necessary to keep the round-trip clean (192 / 193 derivations)

- Phase 10 — Coverage + audit closure
  1. Confirm `aeat audit rulesets citations` reports 100 percent on Modelo 390 (3 ruleset rows × 6 computed casillas × ≥ 1 citation each)
  1. Update `docs/coverage/modelos.md` row for Modelo 390 to ✅ across applicable columns; update provenance line with this issue's reference
  1. Author execution summary `.vault/exec/2026-04-27-modelo-390-calc-verify/2026-04-27-modelo-390-calc-verify-summary.md` with per-year casilla inventory + mutation kill-rate + citation coverage before/after + cumulation design rationale

- Phase 11 — Final QA + commit + PR
  1. Run `just lint && just typecheck && just test && just hooks` until all green
  1. Compose conventional-commit sequence per the handover prompt's recipe
  1. PR body includes `Closes #327`, vault artefact links, parent EPIC reference, M303 + M130 reference impl mentions, BOE source list, casilla classification, cumulation choice rationale, sibling-branch coordination notes for M100 megaproject `#317` on the three shared files

## Parallelization

Phases 2 / 3 (ruleset structure + casilla expansion) must run sequentially because they touch the same files. Phase 4 (extractor) and Phase 8 (reference manifest) can run in parallel with Phase 6 (per-year tests). Phase 7 (cumulation tests) depends on Phase 3 (formulas in place) and Phase 4 (M390 extractor variants registered for 2024 / 2026 if those years are exercised). Phase 9 (integration verification) depends on Phases 2-7. Phase 10 (coverage docs) depends on everything else.

In practice the work is single-file editing per phase, so parallelism is a red herring inside this issue's scope. The shared-file textual unions with sibling branch `feature/317-modelo-100-renta-full-calc` (for `tests/integration/test_kent_workflows.py`, `docs/coverage/modelos.md`, `src/aeat/domain/formulas/_rulesets/__init__.py`) resolve at PR-open time as mechanical merges.

## Self-review against project mandates and the DoD

Reviewed against `CLAUDE.md`, `.claude/rules/vaultspec-system.builtin.md`, the canonical Tier-L bar in EPIC `#316`, and the eight safety invariants enumerated in the handover prompt:

| Invariant | Where it lands |
| :--- | :--- |
| Cent-exact correctness | Per-year worked-example tests + cumulation tests with expected values from BOE rates, not from the ruleset; `tolerance=Decimal("0.01")` |
| External anchoring | Every expected value cites a BOE article in the test docstring; rule-delta manifest cross-references each rate to its `BOE-A-*` id |
| Per-annum coverage | 2024 / 2025 / 2026 rulesets registered with non-overlapping `effective_from/to`; registry `_spans_overlap` gate enforces this |
| `#339` citation enforcement | Every computed casilla bound to ≥ 1 LIVA / RIVA / Orden Ministerial citation; `aeat audit rulesets citations` reports 100 percent |
| `#338` mutation harness ≥ 90 percent | `EXPECTED_COUNTS` updated for the three years; operand-swap tests cover the new sub_op chains; orphan-node defense passes |
| PDF round-trip | `_synth_annual_pdf` already exists; test class generates and round-trips every parametrised case; tampered fixtures produce `CORRECTNESS_DIVERGENCE` |
| Integration test passes | `TestKentImportsModelo390Declaracion` keeps four cases; ASCII-safe assertions on `Extraction status:` / `Verification status:` / `casilla N`; module markers preserved |
| L1 anchor decision | Explicit waiver authored at `.vault/reference/2026-04-27-modelo-390-l1-anchor-waiver-reference.md`; mirrors Modelo 303 pattern |

Project-mandate compliance:

- All Python modules under `src/aeat/`. ✓
- Pydantic v2 strict for boundary models (the helpers in `_common.py` already produce strict models). ✓
- Errors inherit from `aeat.core.errors.AeatError`. No new error subclasses needed. ✓
- Logging via `aeat.core.logging.get_logger`. No new log surfaces. ✓
- Tests `[pytest.mark.unit, pytest.mark.domain_local_state]` at module level (per existing per-modelo pattern). ✓
- No mocks / fakes / stubs / skips. ✓
- No wave / phase numbering in source code or docstrings. The existing `modelo_390_2025.py` wave-numbered comments are scrubbed. ✓
- Google-style docstrings + full type hints on new functions. ✓
- Conventional commits per handover-prompt recipe. ✓

Cross-reference siblings:

- `#317` Modelo 100 RENTA megaproject — different modelo files, soft-collisions on three shared files (`tests/integration/test_kent_workflows.py`, `docs/coverage/modelos.md`, `src/aeat/domain/formulas/_rulesets/__init__.py`) that resolve as additive textual unions. Plan accommodates by keeping changes additive and never deleting M100-specific rows.
- `#321 / #326 / #319 / #322 / #318 / #320` — already landed; consume their patterns directly.
- `#338 / #339 / #340` — landed foundations; consume their invariants.
- `#345` IVA complexity sub-EPIC — out of scope; rule-delta manifest documents deferrals.
- `#437` aggregator-cumulation ADR — not yet landed; this plan picks Approach C deliberately to avoid preempting that ADR's prescription.

## Verification

Mission success criteria:

- Three rulesets registered (`modelo_390.2024`, `modelo_390.2025`, `modelo_390.2026`) with non-overlapping effective ranges.
- 15-casilla surface aligned with the extractor; 6 computed casillas (`104`, `105`, `190`, `191`, `192`, `193`).
- Every computed casilla carries ≥ 1 BOE-anchored `LegalCitation`. `aeat audit rulesets citations` reports 100 percent.
- Per-year unit-test files (`test_modelo_390_2024.py`, `test_modelo_390_2025.py`, `test_modelo_390_2026.py`) covering ≥ 3 parametrised cases per computed casilla, every expected value externally anchored.
- Cumulation test class verifies an annual Modelo 390 fixture round-trips against four synthetic quarterly Modelo 303 fixtures.
- `tests/integration/test_kent_workflows.py::TestKentImportsModelo390Declaracion` four cases pass via Typer `CliRunner`.
- `EXPECTED_COUNTS` map in `test_mutator_kill_rate.py` updated for the three years; mutation aggregate kill-rate ≥ 90 percent on the populated mutator surface.
- Operand-swap mutation tests cover the new sub_op chains for at least one representative year.
- `.vault/reference/2026-04-27-modelo-390-rule-delta-reference.md` lists per-year sameness with BOE citations and cumulation rules.
- `.vault/reference/2026-04-27-modelo-390-l1-anchor-waiver-reference.md` documents the L1 waiver.
- `docs/coverage/modelos.md` Modelo 390 row flipped to ✅ in the applicable columns; provenance line cites this issue.
- `.vault/exec/2026-04-27-modelo-390-calc-verify/2026-04-27-modelo-390-calc-verify-summary.md` captures per-year casilla inventory, BOE source list, citation-coverage before / after, mutation fingerprint, cumulation design rationale.
- `just lint && just typecheck && just test && just hooks` all green.
- Coverage floor 60 percent on `src/aeat/` preserved.

Honest caveats:

- The rate-anchored expected values come from LIVA art. 90 (21 percent) and LIVA art. 91 (10 / 4 percent). The BOE consolidated-text update window for 2026 is verified through the existing Modelo 303 reference (`#326`). No third-party recomputation infrastructure is invoked; the test-level external anchoring is a textual citation rather than a runtime cross-check against AEAT's simulator. This is the same posture every previous Tier-L impl has taken.
- The cumulation test asserts that a specific synthetic-fixture roundup matches the annual Modelo 390 algebraic chain. It does not assert that a *real* taxpayer's four quarterly filings would always sum to a clean Modelo 390, because real-world cumulation includes per-rate-bucket detail in Apartado 3 that the MVP does not model. The cumulation test demonstrates the mechanism; the deeper per-rate-bucket cumulation belongs to `#345`.
- Live AEAT verification is permanently out of scope per the project's safety charter.
