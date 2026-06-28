---
tags:
  - '#plan'
  - '#modelo-130-calc-verify'
date: '2026-04-27'
modified: '2026-04-27'
related:
  - "[[2026-04-27-modelo-130-calc-verify-adr]]"
  - "[[2026-04-27-modelo-130-calc-verify-research]]"
---

# `modelo-130-calc-verify` plan — phase-1

This plan executes the ADR for issue `#321` end-to-end. Phases are
ordered to minimise rebase risk and keep each commit independently
green.

## Phase 1 — back-fill audit on existing 2024 + 2025 rulesets

### Step 1.1 — Audit 2024 ruleset against `#339` citation invariant

Run `uv run aeat audit rulesets citations` and confirm
`modelo_130.2024` reports `coverage=100.00%` (every `computed=True`
casilla has at least one `LegalCitation`). Capture the line of output
in the exec record.

The validator is `_require_legal_basis_for_computed` on
`CasillaDefinition`; an audit pass at `100.00 %` proves no `computed=True`
casilla has empty `legal_basis`. The 2024 ruleset's `_CITATIONS`
already covers RIRPF art. 110 + LIRPF art. 99. No back-fill expected.

### Step 1.2 — Audit 2025 ruleset against `#339` citation invariant

Same as 1.1 for `modelo_130.2025`. The 2025 ruleset re-imports
`_CITATIONS_2024` so the result is identical.

### Step 1.3 — Add threshold-edge cases for casilla-13 minoración (2024 + 2025)

Add a parametrised test
`test_casilla_13_minoracion_brackets_<year>` to each of
`test_modelo_130_2024.py` and `test_modelo_130_2025.py`:

- 8 boundary cases: 8 999,99 / 9 000,00 / 9 000,01 / 10 000,00 /
  10 000,01 / 11 000,00 / 11 000,01 / 12 000,00 / 12 000,01 /
  12 500,00 €.
- Expected values from RIRPF art. 110.3.c verbatim.
- Calls `compute_casilla_13_minoracion` and asserts equality.

Both files keep their existing `pytest.mark.unit,
pytest.mark.domain_local_state` module markers.

**Commit 1.** `chore(rulesets): back-fill modelo 130 2024 + 2025
threshold-edge minoración cases (#321)`.

## Phase 2 — author 2026 ruleset

### Step 2.1 — `src/aeat/domain/formulas/_rulesets/modelo_130_2026.py`

New module mirroring the 2025 file's shape:

- Re-imports `_CASILLAS_2024` + `_CITATIONS_2024` from
  `modelo_130_2024`.
- Declares its own `_FORMULAS` with the
  `modelo_130.2026.<reason>` namespace.
- Declares its own `_PARAMETERS` with `effective_from=2026-01-01` /
  `effective_to=2026-12-31` and the same numerical values
  (`irpf.trimestral_rate=0.20`, `agraria.trimestral_rate=0.02`).
- Exposes `RULESET` with `ruleset_id="modelo_130.2026"`.

Module docstring documents the no-2025-no-2026 amendment finding and
links to the rule-delta manifest.

### Step 2.2 — register in `__init__.py`

Add `from .modelo_130_2026 import RULESET as MODELO_130_2026` and
extend `ALL_RULESETS` + `__all__`. Insert in numerically-ascending
order between `MODELO_130_2025` and `MODELO_131_2024`.

### Step 2.3 — `src/aeat/domain/formulas/_rulesets/test_modelo_130_2026.py`

Mirror `test_modelo_130_2025.py`:

- `_provided()` worked-example fixture (different scenario from 2025
  to avoid mirror-fixture coupling).
- `test_consistent_quarter_is_clean` — happy path.
- `test_agraria_income_computes_2_percent` — agraria worked example.
- `test_2026_no_drift_from_2025` — derived ledger entries equal the
  2025 ruleset's ledger entries on identical inputs (the no-amendment
  invariant).
- `test_ruleset_id_and_effective_range` — id + dates.
- `test_external_worked_example_rirpf_art_110_2026` — external-anchored
  Q3 2026 mixed scenario with non-zero minoración.
- `test_casilla_13_minoracion_brackets_2026` — 10 boundary cases.
- `test_zero_boundary_is_clean` — all zeros.

Module marker: `pytest.mark.unit, pytest.mark.domain_local_state`.

### Step 2.4 — extend `test_mutator_kill_rate.py::EXPECTED_COUNTS`

Add `"modelo_130.2026": {sub_op: 8, percent_rate_literal: 0,
percent_rate_param: 2, percent_rate_compound_skipped: 0,
percent_rate_casilla_ref_skipped: 0,
brackets_threshold_non_terminal: 0, mul_div_scalar: 0}`.

### Step 2.5 — extend `test_operand_swap_mutation.py`

Add 6 × `pytest.param` entries pointed at `MODELO_130_2026` for
casillas 03, 07, 11, 14, 17, 19, reusing
`_modelo_130_rich_fixture()`.

Import `MODELO_130_2026` from the rulesets package.

### Step 2.6 — extend `test_percent_rate_mutation.py`

Add 2 × tuples: `(MODELO_130_2026, "04", _f130_irpf_fixture())` and
`(MODELO_130_2026, "09", _f130_agraria_fixture())`.

Import `MODELO_130_2026`.

**Commit 2.** `feat(rulesets): add modelo 130 2026 ruleset (BOE-stable across 2024/2025/2026) (#321)`.

## Phase 3 — rule-delta manifest

### Step 3.1 — `.vault/reference/2026-04-27-modelo-130-rule-delta-reference.md`

Author the reference document per the ADR D8 structure:

- Frontmatter `tags: [#reference, #modelo-130-calc-verify]`,
  `related:` wiki-links to research + ADR + plan.
- Per-year delta table.
- Diff narrative with BOE citations.
- L1 waiver section.

**Commit 3.** `docs(reference): add 2026-130 rule-delta manifest + L1 waiver (#321)`.

## Phase 4 — synthetic generator + extractor casilla-completeness

### Step 4.1 — extend `modelo_130_generator.py`

Add 12 new `CasillaBox` entries for casillas 08-19 with y_mm pitch
of 10 mm starting at 135 mm. Update `_MODELO_130_BOXES` to 19 entries
and the docstring to reflect the 19-casilla layout.

Audit the existing test calls to ensure no regression: the generator
is called from `tests/integration/test_kent_workflows.py` with a
`casilla_values` mapping that may not include all 19 keys. Confirm
the generator handles missing keys gracefully (it already does —
`params.casilla_values.get(box.casilla_id)` returns `None` and the
`draw_casilla_box` helper is responsible for blank-box handling). If
not, fix that path.

### Step 4.2 — extend `modelo_130_v2025.py` extractor

Add label regexes for casillas 08-19 to `_LABEL_REGEX_MAP`. Keep
`_REQUIRED_FOR_COMPLETE = frozenset({01..07})` unchanged. Update
`_MODELO_130_CASILLAS` to all 19. Update the module docstring.

The structural-integrity check on cas. 03 (`01 - 02 = 03`) remains
in place; no equivalent for the other computed casillas at the
extractor layer (those are verified by the ruleset engine
post-extraction).

### Step 4.3 — colocated extractor test (if missing) or extend existing

Verify if `src/aeat/adapters/inbound/declaracion/_extractors/test_modelo_130_v2025.py`
exists (or similar). If yes, extend its parametrisation to 19 casillas;
if no, ship a minimal one that round-trips a 19-casilla synthetic PDF
through `Modelo130V2025Extractor.extract` and asserts every casilla
parses.

**Commit 4.** `feat(declaracion,testing): expand modelo 130 generator + extractor to 19 casillas (#321)`.

## Phase 5 — integration test 4th case

### Step 5.1 — `test_discrepancy_classified_correctly`

Add to `TestKentImportsModelo130Declaracion` in
`tests/integration/test_kent_workflows.py`:

- Generate a PDF where `04 = 1 800,00` instead of the engine-
  re-derived `04 = 2 000,00` (a 200,00 € drift on a 03 = 10 000,00
  rendimiento neto).
- Run `aeat filing import --from-declaracion` via `CliRunner`.
- Assert `Verification status: NEEDS_REVIEW` AND a casilla-04
  reference appears in the output.
- Assert exit code 0 (the discrepancy is reported, not raised).

Spanish-default + explicit-English variants both — match the existing
3 mandatory cases' shape.

**Commit 5.** `test(integration): add discrepancy classified case for modelo 130 (#321)`.

## Phase 6 — coverage docs flip + exec records

### Step 6.1 — `docs/coverage/modelos.md`

Flip M130 row to ✅ across applicable columns. Add a provenance line
citing `Closes #321`.

### Step 6.2 — `.vault/exec/2026-04-27-modelo-130-calc-verify/`

Create the exec folder + step records + summary. Capture:

- Per-year casilla inventory.
- Mutation kill-rate (run the harness; record output).
- BOE source list with article + URL where available.
- Citation-pending casillas (none expected; if any, file follow-up
  issue).
- L1 anchor decision (waiver).
- `aeat audit rulesets citations` output before + after.

**Commit 6.** `docs(coverage,exec): modelo 130 verify-roundtrip records (#321)`.

## Phase 7 — quality gates + code review

### Step 7.1 — `just lint && just typecheck && just test && just hooks`

All four green on Windows. Coverage floor 60 % preserved on
`src/aeat`.

### Step 7.2 — citation audit

Re-run `uv run aeat audit rulesets citations`. Confirm all
M130 rulesets (2024, 2025, 2026) report `coverage=100.00%`.

### Step 7.3 — mutation kill-rate

Run the mutation harness:
`just test src/aeat/domain/formulas/_rulesets/test_*_mutation.py
src/aeat/domain/formulas/_rulesets/test_mutator_kill_rate.py`.
Confirm aggregate kill-rate ≥ 90 % (and the per-class harnesses pass
on M130 nodes).

### Step 7.4 — `vaultspec-code-review` self-review

Walk the 8 safety invariants documented in the handover STEP 2:

1. **Cent-exact correctness** — every `computed=True` casilla
   produces values within ±0.01 € of the externally-anchored
   expected value across every parametrised case.
2. **External anchoring** — every expected value cites a verifiable
   external source (RIRPF art. 110 / LIRPF art. 99). NO internally-
   computed expected values.
3. **Per-annum coverage** — 2024, 2025, 2026 rulesets each
   registered as separate files with non-overlapping
   `effective_from/to` windows.
4. **`#339` citation enforcement passes** — every
   `CasillaDefinition.legal_basis` is non-empty on `computed=True`
   rows; every `LegalCitation.source` is a valid
   `LegalCitationSource` enum member; every citation passes the
   `KnownBadCitation` blocklist; running `aeat audit rulesets
   citations` shows 100 % coverage on M130.
5. **`#338` mutation harness coverage** — every PercentFormula,
   BracketsFormula, MulFormula, DivFormula, SubFormula in the M130
   rulesets is exercised; aggregate kill-rate ≥ 90 % on M130 nodes;
   the orphan-node defense (`test_mutator_exhaustiveness.py`) still
   passes.
6. **PDF round-trip closes** — synthetic `generator(params) → PDF →
   extractor` returns the same `params`; `verify_declaracion(filing,
   ruleset)` returns `VERIFIED` on the synthetic happy path;
   tampered fixtures produce correctly-classified
   `ClassifiedDiscrepancy`.
7. **Integration test passes via `CliRunner`** —
   `TestKentImportsModelo130Declaracion` with at least 3 cases
   (english, spanish-default, partial-extraction) + optional 4th
   (`test_discrepancy_classified_correctly`); ASCII-safe substring
   assertions; markers preserved at module level.
8. **L1 anchor decision documented** — explicit waiver in
   `.vault/reference/2026-04-27-modelo-130-rule-delta-reference.md`.

## Self-review against CLAUDE.md + `aeat-project-mandates.md`

### Conventions

- ✅ Python modules under `src/aeat/<subpackage>/` only — the new
  ruleset lives at `src/aeat/domain/formulas/_rulesets/modelo_130_2026.py`.
- ✅ Public API discipline — callers import from `aeat.domain.formulas`,
  `aeat.adapters.inbound.declaracion`, `aeat.domain.testing` only. The new ruleset is
  re-exported via `aeat.domain.formulas._rulesets.__init__`.
- ✅ Pydantic v2 strict — `CasillaDefinition`, `LegalCitation`,
  `Ruleset`, `ParameterTable`, `Modelo130GenParams` already strict;
  no new boundary-crossing types in this issue.
- ✅ Errors inherit from `aeat.core.errors.AeatError` — no new exceptions
  raised in this issue (the existing `RulesetValidationError` is the
  only failure mode of `_require_legal_basis_for_computed`).
- ✅ Logging via `aeat.core.logging.get_logger(__name__)` only — no new
  logger calls in this issue.
- ✅ Pytest markers at MODULE level — the new ruleset test file uses
  `pytestmark = [pytest.mark.unit, pytest.mark.domain_local_state]`.
- ✅ Live tests N/A — no AEAT I/O.
- ✅ Trilingual — `_provided()` and worked-example fixtures are
  numeric only; no new user-facing strings.
- ✅ Live-submit-forbidden — this issue touches verification only;
  no test, doc, or comment frames any future live-submission. The
  product is `produce → verify → export`.
- ✅ Google-style docstrings + full type hints on every public
  symbol.
- ✅ `ty` (not mypy), `prek` (not pre-commit) — `just typecheck`
  uses `ty`; `just hooks` runs `prek`.
- ✅ Conventional commits — every commit message is
  `<type>(<scope>): <subject>`.
- ✅ Actions CI — no new workflow files; `.github/workflows/ci.yml`
  re-runs the four gates on PR.

### No-mocks discipline

- ✅ `test_modelo_130_2026.py` uses real `Engine`, real `Ruleset`,
  real `CasillaDefinition`, real `LegalCitation`, real
  `ParameterTable`. No `unittest.mock`, `pytest_mock`,
  `time_machine`, `freezegun`, or `vcr`.
- ✅ The integration test 4th case uses `Typer.testing.CliRunner`
  + real synthetic PDF generation via `aeat.domain.testing` factories. No
  mocked filesystem or subprocess.
- ✅ The mutation harness extensions reuse the existing `_modelo_130_*`
  fixtures (they are real ruleset evaluations under
  `Engine.audit_against`, not mocks).

### Lint / typecheck / test / hooks

- ✅ `just lint` — `ruff` + `ruff-format`. The new files follow the
  existing 2024 / 2025 module's line-length (~100), import order
  (`from __future__ import annotations`, stdlib, third-party, local),
  and docstring style.
- ✅ `just typecheck` — `ty` strict. `Decimal` everywhere; no `Any`.
- ✅ `just test` — `pytest -m unit` per `addopts`.
- ✅ `just hooks` — `prek` + `check-added-large-files` (500 KB cap).
  No file in this issue approaches 500 KB.

### Coverage

- ✅ 60 % floor on `src/aeat` preserved. The new module is a
  structural clone of an existing module (mostly imports + a
  ParameterTable + 9 formula-builder calls); the new test file is
  ~150 lines covering every formula + the minoración helper. Net
  effect on overall coverage is positive — every line of the new
  module is exercised by the new test file.

## Self-review — out-of-scope guards

Per ADR § Out of scope, this plan **does not touch**:

- Any other Tier-L modelo (#317, #318, #319, #320, #322, #323, #324,
  #325, #326, #327).
- Tier-S (#328-#331) or Tier-R (#332-#337).
- Any sub-umbrella (#341, #345).
- `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/sede/`, `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_clave_movil.py`,
  `src/aeat/entrypoints/cli/sede/`, `src/aeat/entrypoints/cli/sanitize/`,
  `src/aeat/entrypoints/cli/filing/_reconcile.py`,
  `src/aeat/domain/justificante/_extract.py`.
- `src/aeat/core/errors/_registry.py` or any error-registry surface.
- `--json` schemas / exit-code table.
- `src/aeat/entrypoints/cli/audit/__init__.py` or `src/aeat/entrypoints/cli/__init__.py`.
- The live-submit forbidden enforcement sweep (#432).
- Any new CLI commands or root-level Typer changes.

## Plan-review outcome

**Approved for execution.** All eight safety invariants have a clear
implementation step. Out-of-scope guards documented. Quality gates
defined. Conventional commit boundaries set. The plan is consistent
with the ADR and the project mandates.

The only deviation from the issue body is the marker convention —
`domain_local_state` (matching the existing per-ruleset test files)
instead of `domain_submission` (matching the issue body's verbatim
instruction). This is justified in the ADR § D4 against the
pyproject-defined marker semantics; the divergence keeps the
rulesets directory internally consistent.
