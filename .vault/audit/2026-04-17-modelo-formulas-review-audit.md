---
tags:
  - '#audit'
  - '#modelo-formulas'
date: '2026-04-17'
modified: '2026-04-17'
related:
  - '[[2026-04-17-modelo-formulas-adr]]'
  - '[[2026-04-17-modelo-formulas-plan]]'
  - '[[2026-04-17-modelo-formula-ruleset-research]]'
---

# modelo-formulas code review (Issue #173)

**Branch:** `feature/173-modelo-formulas`
**Reviewer:** vaultspec-code-reviewer (autonomous persona)
**Date:** 2026-04-17
**Commits audited:**
- `fba56bd test(formulas): unit tests for engine + Modelo 130 (#173)`
- `b0b926c feat(formulas): wire aeat formulas CLI subcommand (#173)`
- `c55b899 feat(formulas): codify Modelo 130 2024 + 2025 rulesets (#173)`
- `602a233 feat(formulas): add period-aware formula engine core (#173)`
- `e7110fb feat(errors): add FormulasError hierarchy (#173)`
- `83fa03a docs(plan): address plan-audit blockers`
- `23091d3 docs(plan): modelo-formulas wave-1 implementation plan`
- `1d7cd15 docs(adr): accept modelo-formulas engine ADR`
- `524cbda docs(research): modelo-formulas ruleset + engine research`

## Summary

The `aeat.domain.formulas` subpackage lands cleanly as a deterministic,
sandboxed, period-versioned formula engine with Modelo 130 (2024 and
2025) as the proof-of-concept ruleset. The implementation faithfully
mirrors the ADR: closed-operator pydantic DSL, `graphlib.TopologicalSorter`
as the sole evaluator, `Decimal`-only arithmetic, terminal
`ROUND_HALF_UP`, single-rounding invariant enforced at load time,
trilingual labels with Spanish authoritativeness, relative imports
throughout, errors rooted at `aeat.core.errors.AeatError`.

**81/81 colocated unit tests pass (~0.7 s)**; `ruff check` is clean;
`ty check` is clean across the whole project; the `aeat formulas
{list,show,compute,audit}` CLI emits deterministic JSON and exits
non-zero with `--strict` on discrepancy. The PR respects its wave-1
boundary: zero changes to `aeat.domain.casillas`, `aeat.application.filing._builders`,
or `corpus/casillas/`.

## Strengths

- **Safety & determinism.** No `eval` / `exec` / `compile` /
  `ast.parse` / `__import__` anywhere in `src/aeat/domain/formulas/`.
  `graphlib.TopologicalSorter` is the only evaluator; cycles raise
  `FormulaCycleError` at `Ruleset` load time
  (`_ruleset.py:163-173`). Engine runs inside
  `decimal.localcontext(prec=28)` (`_engine.py:80-81`).
- **Decimal discipline.** `_coerce_decimal` rejects `float` and
  `bool` explicitly (`_formula.py:25-42`). `DivFormula` requires
  an explicit quantize at 4 dp. Compound operators never round;
  `RoundFormula` is wrapped around every `FormulaDefinition` via
  `_rulesets/_common.formula()`, producing a single terminal ROUND
  per computed casilla. `RoundFormula._reject_nested_round`
  enforces the single-rounding invariant recursively.
- **Pydantic mandate.** Every model in the subpackage carries
  `ConfigDict(strict=True, frozen=True, extra="forbid")` (11
  occurrences across 6 model modules). Discriminated unions use
  `Field(discriminator="op")` for both `Formula` and `Operand`.
  `model_rebuild()` called on every variant to resolve the
  self-referential `Operand` alias.
- **Relative imports.** Every internal import inside
  `src/aeat/domain/formulas/` is relative. The CLI shim
  `src/aeat/entrypoints/cli/formulas.py:9` uses `from ..formulas._cli import app`.
  No `aeat.*` absolute imports in production code.
- **Public-API discipline.** Cross-subpackage imports always
  use the package root: `from ..casillas import CasillaDataType`,
  `from ..i18n import Translatable, require_authoritative`,
  `from ..models import LegalCitation, LegalCitationSource,
  ModeloCode`. The registry binds to `aeat.domain.modelos.ModeloCode`
  (authoritative), never to the `aeat.domain.casillas.models.ModeloCode`
  restricted enum (integration test enforces).
- **Trilingual contract.** `CasillaDefinition.label: Translatable`;
  `require_authoritative(..., domain="aeat")` invoked in a
  `model_validator`. Every Modelo 130 casilla ships es/en/hu
  labels.
- **Errors.** All 8 formula-domain errors live in
  `src/aeat/errors.py:78-132` under a single `FormulasError(AeatError)`
  root, exactly as specified (no rogue `_errors.py` inside the
  subpackage).
- **Logging.** `aeat.core.logging.get_logger(__name__)` used
  (`_engine.py:22, 45`); one INFO per `derive`; DEBUG per defaulted
  input. No `print` calls.
- **Testing mandate.** `@pytest.mark.unit` on every test; colocated
  in `src/aeat/domain/formulas/test_*.py`; no `mock`, `patch`, `MagicMock`,
  `pytest_mock`, or `monkeypatch.setattr` usage. Expected values
  hand-computed as `Decimal` strings.
- **Ruleset correctness.** The 9 computed formulas match the
  research doc verbatim: 03=01-02; 04=max(0, 0.20*03); 07=04-05-06;
  09=0.02*08; 11=09-10; 12=max(0, 07+11); 14=12-13; 17=14-15-16;
  19=17-18 — each wrapped in a terminal `RoundFormula(digits=2)`.
  A live `Engine.derive` with `{01: 12000, 02: 3500, 06: 500}`
  emits 03=8500.00, 04=1700.00, 07=1200.00, 12=1200.00, 19=1200.00
  — matches the plan's hand-computed expectations.
- **Legal citations.** Every casilla carries a citation pointing
  to `LegalCitationSource.REAL_DECRETO` art. 110 (RIRPF); the
  ruleset root also cites `LegalCitationSource.LEY` art. 99
  (LIRPF).
- **CLI wiring.** `aeat formulas list` returns the expected
  2-ruleset JSON payload. `--strict` audit path exits with code 3
  on discrepancy (`_cli.py:162-166`).
- **Scope compliance.**
  `git diff --stat main -- src/aeat/casillas src/aeat/filing
  corpus/casillas` is empty.

## Blocking issues

**None.** No CRITICAL or HIGH findings.

## Non-blocking concerns (documented for future waves)

- **LOW — Ledger ordering surprises humans.**
  `ComputationLedger.entries` follows `graphlib` topological
  order, interleaving Apartado-II casillas (09, 11) between 03
  and 07 rather than the natural reading order. Deterministic and
  correct per the ADR, but consumers may expect casilla-id-
  ascending output. Consider an optional
  `ledger.sorted_by_casilla_id()` view in a future wave.
- **LOW — `LedgerEntry.operand_values` silently filters.**
  `_engine.py:98` `ref_values = tuple(values[ref] for ref in refs
  if ref in values)` — today every ref resolves (post-order
  guaranteed), so the filter is latent. Prefer an explicit
  `KeyError`-raising path to act as a future guardrail.
- **LOW — `_spans_overlap` double-`None` branch is untested.**
  `_registry.py:65-66` correctly returns `True` when both
  `effective_to=None`, but no unit case covers that branch. Add
  one belt-and-braces test.
- **LOW — `_cli.py:_parse_kv_pairs` uses bare `except Exception`.**
  Narrow to `decimal.InvalidOperation` to avoid swallowing
  programmer errors.
- **LOW — `Engine._reject_non_decimal` re-checks typed inputs.**
  Intentional runtime guard for future untyped callers (e.g.,
  JSON loaders); a one-line comment would make the intent
  explicit.
- **MEDIUM — `compute_casilla_13_minoracion` bypasses the engine.**
  It walks a local `_CASILLA_13_BRACKETS` tuple with plain Python
  rather than routing through a `BracketsFormula` node.
  Functionally equivalent and the plan's §Risks section documents
  this, but it leaves the `BRACKETS` operator with no production
  caller in wave 1 — only unit tests exercise it. Acceptable per
  the ADR's "minimal-viable operator surface" discipline; flag
  for wave 3 (Modelo 100) where BRACKETS becomes load-bearing.

## Verdict

**ACCEPT.**

Wave 1 delivers the ADR's entire contract with no safety
regressions, no architectural drift, no scope creep, and full test
coverage of the critical paths (81/81 pass, ruff clean, ty clean).
The non-blocking notes are documentation / future-proofing items;
none block merge. A future wave that wires the new engine into
`aeat.application.filing._builders.modelo_130` or adds Modelo 303 should
revisit the MEDIUM note on `BracketsFormula` production exercise.
