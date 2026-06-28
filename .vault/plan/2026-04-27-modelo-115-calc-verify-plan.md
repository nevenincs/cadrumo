---
tags:
  - '#plan'
  - '#modelo-115-calc-verify'
date: '2026-04-27'
modified: '2026-04-27'
related:
  - "[[2026-04-27-modelo-115-calc-verify-research]]"
  - "[[2026-04-27-modelo-115-calc-verify-adr]]"
  - "[[2026-04-27-modelo-130-calc-verify-plan]]"
  - "[[2026-04-27-modelo-130-rule-delta-reference]]"
---

# `modelo-115-calc-verify` plan — issue `#319`

This plan executes the decisions in
`2026-04-27-modelo-115-calc-verify-adr` for issue `#319` on
branch `feature/319-modelo-115-calc-verify`. The work mirrors the
M130 reference implementation
(`2026-04-27-modelo-130-calc-verify-plan`) on a smaller surface
(2 computed casillas vs M130's 9; 6 total vs 19).

## Phase 1 — 2026 ruleset + rule-delta manifest

### Step 1.1 — Author `modelo_115_2026.py`

- File: `src/aeat/domain/formulas/_rulesets/modelo_115_2026.py`.
- Pattern: re-import-clone of 2025, mirroring `modelo_115_2024.py`.
- Effective range: 2026-01-01 → 2026-12-31.
- `irpf.arrendamientos_rate = Decimal("0.19")`.
- Module docstring quotes the BOE consolidated text last-update
  date 2026-02-28 and the verbatim art. 100 ¶ 1 statute.
- Re-imports `_CASILLAS_2025`, `_CITATIONS_2025`, `_FORMULAS_2025`
  from `modelo_115_2025`.

### Step 1.2 — Register `MODELO_115_2026` in `__init__.py`

- File: `src/aeat/domain/formulas/_rulesets/__init__.py`.
- Add `from .modelo_115_2026 import RULESET as MODELO_115_2026`.
- Insert into `ALL_RULESETS` (after `MODELO_115_2025`, before
  `MODELO_123_2024`).
- Insert into `__all__` (alphabetical-numeric position).
- Update the wave-42-M1 docstring blurb to mention M115 2026
  alongside M130 2026.

### Step 1.3 — Author `2026-115-rule-delta.md`

- File: `.vault/reference/2026-115-rule-delta.md`.
- Use `vault add reference --feature modelo-115-calc-verify`
  scaffold; replace placeholders with content per ADR §D3.
- Mirror `.vault/reference/2026-130-rule-delta.md` structure
  exactly (statutory grounding table, per-year numerical state
  table, 2024 → 2025 + 2025 → 2026 diff narratives, mutation
  fingerprint, citation completeness, L1 waiver, audit trail).

### Step 1.4 — Mutation harness rows for 2026

- File: `src/aeat/domain/formulas/_rulesets/test_mutator_kill_rate.py`.
  Add `"modelo_115.2026"` row to `EXPECTED_COUNTS` mirroring the
  2024 / 2025 rows (`sub_op=1, percent_rate_param=1`, all others
  zero).
- File:
  `src/aeat/domain/formulas/_rulesets/test_percent_rate_mutation.py`.
  Add `(MODELO_115_2026, "03", _f115_fixture())` to
  `_ruleset_cases` after the 2025 row. Update import to include
  `MODELO_115_2026`.
- File:
  `src/aeat/domain/formulas/_rulesets/test_operand_swap_mutation.py`.
  Add a 2026 entry under the wave-75a parametrise block reusing
  `_modelo_115_fixture`. Update import to include
  `MODELO_115_2026`.

### Step 1.5 — Per-year worked example test for 2026

- File:
  `src/aeat/domain/formulas/_rulesets/test_modelo_115_2026.py` (NEW).
- Mirror `test_modelo_130_2026.py` structure on the smaller M115
  surface:
  - `_provided()` helper returning a clean Q3 2026 fixture (the
    24 000 € / 250 € / 100 € scenario from the research doc).
  - `TestModelo115Ruleset2026` class with:
    - `test_consistent_quarter_is_clean`
    - `test_2026_no_drift_from_2025` (no-drift assertion per ADR §D6)
    - `test_ruleset_id_and_effective_range`
    - `test_external_worked_example_rirpf_art_100_2026` (per ADR §D5)
    - `test_retention_rate_mismatch_raises` (negative path)
- Module marker `[pytest.mark.unit, pytest.mark.domain_local_state]`.

### Step 1.6 — Commit cluster A

- `feat(rulesets): add modelo 115 2026 ruleset (BOE primary-sourced retention rate) (#319)`
  — bundles 1.1 + 1.2.
- `docs(reference): add 2026-115 rule-delta manifest (#319)`
  — 1.3.
- `test(formulas): worked examples for modelo 115 2026 ruleset (#319)`
  — 1.5 + 1.4.

## Phase 2 — Extractor sibling classes (2024 + 2026)

### Step 2.1 — Add sibling classes to `modelo_115_v2025.py`

- File: `src/aeat/adapters/inbound/declaracion/_extractors/modelo_115_v2025.py`.
- After `Modelo115V2025Extractor`, add
  `Modelo115V2024Extractor(Modelo115V2025Extractor)` and
  `Modelo115V2026Extractor(Modelo115V2025Extractor)` siblings.
- Each pins only its own
  `template_revision = TemplateRevision(modelo="115", año=YYYY,
  revision=f"{YYYY}.01")`.
- Update module docstring to note the extractor backs three years
  (2024 / 2025 / 2026 share the AEAT layout per the rule-delta
  manifest).
- Update `__all__` to include all three classes.

### Step 2.2 — Register sibling classes

- File:
  `src/aeat/adapters/inbound/declaracion/_extractors/__init__.py`.
- Update import `from .modelo_115_v2025 import (...)` to bring in
  `Modelo115V2024Extractor` + `Modelo115V2026Extractor`.
- Add both to `_REGISTERED_CLASSES` (after the existing
  `Modelo115V2025Extractor` entry, alphabetical-numeric position
  preserved — same layout as the M130 sibling block).

### Step 2.3 — Commit cluster B

- `feat(declaracion): register modelo 115 V2024 + V2026 extractors (#319)`.

## Phase 3 — Integration test parametrisation

### Step 3.1 — Add `test_per_year_happy_path_verified` to M115 class

- File: `tests/integration/test_kent_workflows.py`.
- Inside `TestKentImportsModelo115Declaracion`, add a parametrised
  case mirroring M130's lines 224..256:
  - `@pytest.mark.parametrize("ejercicio", ["2024", "2025", "2026"])`
  - Generates a synthetic PDF via `_synth_quarterly_pdf` with
    `año=int(ejercicio)`, `ejercicio=ejercicio`,
    `template_revision=f"{ejercicio}.01"`.
  - Runs `aeat filing import --from-declaracion <pdf>`.
  - Asserts `Extraction status: COMPLETE`,
    `Verification status: VERIFIED`, and
    `f"Modelo 115 {ejercicio}Q1"` substring in output.
- Position: after `test_partial_extraction_needs_review`, before
  the existing `test_discrepancy_classified_correctly`.

### Step 3.2 — Commit cluster C

- `test(integration): per-year happy-path coverage for modelo 115 (#319)`.

## Phase 4 — Coverage docs flip

### Step 4.1 — `docs/coverage/modelos.md`

- File: `docs/coverage/modelos.md`.
- Replace the row 13 (M115) emoji set with the new state:
  - per-annum coverage column → `✅ (2024 + 2025 + 2026)`
  - mutation column → `✅ (per-class harness)`
  - integration column → `✅ (4 cases + per-year)`
  - L1 anchor column → `❌ (waiver — see 2026-115-rule-delta)`
  - others → preserve current state unless this PR explicitly
    completes them.
- Append the provenance line at the bottom of the file describing
  this PR (`Closes #319`), citing the BOE primary source for the
  19 % rate and the no-drift narrative.

### Step 4.2 — Commit cluster D

- `docs(coverage): flip modelo 115 row to verified (#319)`.

## Phase 5 — Verification + exec records

### Step 5.1 — Run audit + tests

- `uv run aeat audit rulesets citations` — confirm
  `modelo_115.2026` reports `OK ... coverage=100.00%` and the
  aggregate stays at 100 %.
- `uv run pytest src/aeat/domain/formulas/_rulesets/test_modelo_115_2026.py`
  — confirm the new module passes.
- `uv run pytest src/aeat/domain/formulas/_rulesets/test_mutator_kill_rate.py`
  — confirm the new EXPECTED_COUNTS row matches actual.
- `uv run pytest src/aeat/domain/formulas/_rulesets/test_percent_rate_mutation.py
  src/aeat/domain/formulas/_rulesets/test_operand_swap_mutation.py`
  — confirm the new 2026 cases kill their mutants.
- `uv run pytest tests/integration/test_kent_workflows.py::TestKentImportsModelo115Declaracion`
  — confirm the per-year parametrisation passes.
- `just lint && just typecheck && just test && just hooks` — full
  pre-commit gate.

### Step 5.2 — Author exec records

- `.vault/exec/2026-04-27-modelo-115-calc-verify/2026-04-27-modelo-115-calc-verify-phase-1-step-ruleset-2026.md`
- `.vault/exec/2026-04-27-modelo-115-calc-verify/2026-04-27-modelo-115-calc-verify-phase-2-step-extractor-siblings.md`
- `.vault/exec/2026-04-27-modelo-115-calc-verify/2026-04-27-modelo-115-calc-verify-phase-3-step-integration.md`
- `.vault/exec/2026-04-27-modelo-115-calc-verify/2026-04-27-modelo-115-calc-verify-summary.md`

### Step 5.3 — Code review

Run the `vaultspec-code-review` skill against every file changed
on the branch; verify the eight safety invariants from the
handover prompt:

1. Cent-exact correctness across every parametrised case.
2. External anchoring of every expected value.
3. Per-annum coverage 2024 / 2025 / 2026 with non-overlapping
   ranges.
4. `aeat audit rulesets citations` reports 100 % on M115.
5. Mutation harness flags every M115 mutable node (kill-rate
   100 % on 2 mutable nodes per ruleset = ≥ 90 % bar).
6. PDF round-trip closes via the `_synth_quarterly_pdf` helper +
   `Modelo115V202[4-6]Extractor`.
7. Integration test passes via Typer CliRunner.
8. L1 waiver documented in the rule-delta manifest.

## Plan self-review

Self-reviewed against:

- `2026-04-27-modelo-115-calc-verify-adr` decisions D1..D12 —
  every decision has a corresponding step.
- M130 reference implementation (`2026-04-27-modelo-130-calc-verify-plan`)
  — every M130 phase has an M115 analogue except the casilla-13
  bracket helper (M115 has no brackets) and the 12-casilla
  extractor extension (M115's 6 casillas are already
  full-coverage in `Modelo115V2025Extractor`).
- The eight safety invariants from STEP 2 of the handover prompt.
- No-mocks discipline.
- No wave / phase numbering in source code (the docstrings cite
  BOE references and architectural reasoning, not delivery
  cadence).
- Project mandate compliance: pydantic v2, errors via
  `aeat.core.errors.AeatError`, logging via `aeat.core.logging.get_logger`,
  trilingual labels, Google-style docstrings, test markers at
  module level.
- Coverage floor 60 % preserved (the new test module and
  parametrised cases only add coverage; nothing is removed).

## Out of scope (re-iterated)

Per ADR §D12 — every other Tier-L modelo, Tier-S, Tier-R, sub-
umbrellas, M111, M180, Ceuta / Melilla overlay, live-submit
sweep (`#432`), root-level CLI changes, storage / financial /
auth / observability surfaces.
