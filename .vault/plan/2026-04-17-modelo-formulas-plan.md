---
tags:
  - '#plan'
  - '#modelo-formulas'
date: '2026-04-17'
modified: '2026-06-13'
related:
  - '[[2026-04-17-modelo-formulas-adr]]'
  - '[[2026-04-17-modelo-formula-ruleset-research]]'
  - '[[2026-04-13-modelo-inventory-adr]]'
  - '[[2026-04-12-casilla-db-adr]]'
  - '[[2026-04-12-filing-draft-engine-adr]]'
  - '[[2026-04-17-relative-imports-adr]]'
---

# modelo-formulas implementation plan

Implements the `aeat.domain.formulas` subpackage per the matching ADR
`[[2026-04-17-modelo-formulas-adr]]`: a deterministic, sandboxed,
period-aware tax-formula engine with a Modelo 130 (2024 and 2025)
ruleset as the proof-of-concept. Wave 1 scope only — future waves
(Modelo 303, 100, 390, …) are explicitly deferred.

## Proposed Changes

- New subpackage `src/aeat/domain/formulas/` with: `_codes.py`,
  `_casilla.py`, `_formula.py`, `_period.py`, `_ruleset.py`,
  `_registry.py`, `_ledger.py`, `_engine.py`,
  `_rulesets/` (two rulesets + shared helpers),
  `_cli.py`, colocated `test_*.py` files, and a thin public API
  re-exported from `src/aeat/domain/formulas/__init__.py`.
  **Error types live in `src/aeat/errors.py`** (project-wide
  mandate: "All domain errors inherit from
  `aeat.core.errors.AeatError`"); the subpackage has **no
  `_errors.py`**.
- New CLI shim `src/aeat/entrypoints/cli/formulas.py` mirroring the `modelos`
  shim pattern.
- Wire the shim into `src/aeat/entrypoints/cli/__init__.py`.
- `src/aeat/errors.py` gains a `FormulasError` subclass hierarchy
  root (kept in `aeat.core.errors` per the cross-subpackage base-class
  pattern).
- `.env.example` is NOT modified — wave 1 introduces no settings.
- `corpus/casillas/` is NOT modified — wave 1 does not rewrite
  the casilla corpus; that lands in a future wave that re-plumbs
  `aeat.domain.casillas` onto `aeat.domain.formulas`.
- `src/aeat/application/filing/_builders/modelo_130.py` is NOT modified —
  the synthetic builder remains; swapping it to the new engine
  is a follow-up issue.
- All internal imports inside `src/aeat/domain/formulas/` use relative
  syntax per the #162 relative-imports mandate.
- Conventional-commit messages throughout.

## Tasks

- `Phase 1 — Error hierarchy + scaffolding`
  1. Add `FormulasError` base + subclasses to `src/aeat/errors.py`
     (`RulesetValidationError`, `FormulaCycleError`,
     `CasillaNotDefinedError`, `AmbiguousPeriodError`,
     `MissingRulesetError`, `EvaluationError`,
     `AuditDiscrepancyError`). Keep them grouped under a clear
     comment block so the file stays navigable.
  2. Create `src/aeat/domain/formulas/__init__.py` (empty stub for now).
  3. Create `src/aeat/domain/formulas/_codes.py` with the `FormulaOp`
     StrEnum (13 members exactly — LITERAL, CASILLA_REF,
     PARAM_REF, ADD, SUB, MUL, DIV, MIN, MAX, CLAMP_POSITIVE,
     PERCENT, BRACKETS, ROUND; plus `Quarter` enum: Q1..Q4).
  4. Create `src/aeat/domain/formulas/_period.py` with `FiscalPeriod`
     (pydantic v2, strict, frozen): `year: int` (1990–2100 bounds),
     `quarter: Quarter | None`, `.start: date`, `.end: date`
     computed fields. `.contains(other: date) -> bool` helper.
- `Phase 2 — Core models`
  1. Create `src/aeat/domain/formulas/_casilla.py` with
     `CasillaDefinition` (strict pydantic v2 frozen):
     `casilla_id: str`, `label: Translatable` (require
     authoritative Spanish via `require_authoritative`),
     `computed: bool`, `data_type: CasillaDataType` (reuse
     existing enum from `aeat.domain.casillas`),
     `legal_basis: tuple[LegalCitation, ...]`,
     `notes_es: str | None`.
  2. Create `src/aeat/domain/formulas/_formula.py` with:
     - `Literal(value: Decimal)` with a string-to-Decimal
       coercion `BeforeValidator` that REJECTS floats.
     - `CasillaRef(casilla_id: str)`.
     - `ParamRef(param_id: str)`.
     - `Formula` — an `Annotated[Union[AddFormula,
       SubFormula, ...], Field(discriminator="op")]` with one
       subclass per `FormulaOp` enum value:
       `AddFormula(op=Literal[FormulaOp.ADD],
       operands: tuple[Operand, ...])`,
       `SubFormula(op=Literal[FormulaOp.SUB],
       operands: tuple[Operand, Operand])`,
       `MulFormula`, `DivFormula` (extra
       `quantize: Decimal = Decimal("0.0001")` field),
       `MinFormula`, `MaxFormula`, `ClampPositiveFormula`
       (unary), `PercentFormula(operands: tuple[Operand,
       Operand])` (rate, base; must evaluate as `rate * base`),
       `BracketsFormula(operands: tuple[Operand],
       brackets: tuple[Bracket, ...])`,
       `RoundFormula(operands: tuple[Operand],
       digits: int = 2, rounding: str = "ROUND_HALF_UP")`.
     - `Operand = Annotated[Union[Literal, CasillaRef,
       ParamRef, Formula], Field(discriminator=...)]`.
     - `FormulaDefinition(casilla_id: str, formula: Formula,
       formula_id: str)`.
  3. Create `src/aeat/domain/formulas/_ruleset.py` with:
     - `ParameterValue(effective_from: date, effective_to:
       date | None, value: Decimal)`.
     - `ParameterTable(entries: Mapping[str, tuple[
       ParameterValue, ...]])` with `.resolve(name, on: date)
       -> Decimal`; raises `MissingRulesetError` on unknown
       parameter, raises `AmbiguousPeriodError` on multi-hit.
     - `Ruleset(ruleset_id, modelo: ModeloCode, effective_from,
       effective_to, casillas, formulas, parameters,
       legal_citations)` with invariants:
       - Every `FormulaDefinition.casilla_id` exists in
         `casillas` and that casilla has `computed=True`.
       - Every `CasillaRef` in any formula resolves inside
         `casillas`.
       - Every `ParamRef` in any formula resolves inside
         `parameters`.
       - No nested `ROUND` inside another `ROUND`
         (single-rounding invariant).
       - DAG is acyclic (build `TopologicalSorter` and call
         `prepare()` in `model_post_init`; wrap `CycleError`
         into `FormulaCycleError`).
  4. Create `src/aeat/domain/formulas/_registry.py` with:
     - `RulesetRegistry(rulesets: tuple[Ruleset, ...])` pydantic
       model; `.resolve(modelo: ModeloCode, period:
       FiscalPeriod) -> Ruleset`.
     - `get_registry() -> RulesetRegistry` helper that
       imports every ruleset in `_rulesets/` once and returns
       the frozen registry.
- `Phase 3 — Ledger + engine`
  1. Create `src/aeat/domain/formulas/_ledger.py` with `LedgerEntry`,
     `ComputationLedger(entries: tuple[LedgerEntry, ...])`,
     `Discrepancy`, `AuditReport(ledger, discrepancies)`;
     `AuditReport.assert_clean()` raises
     `AuditDiscrepancyError` when non-empty.
  2. Create `src/aeat/domain/formulas/_engine.py` with the
     `Engine` facade:
     - `derive(*, ruleset: Ruleset, inputs: Mapping[str,
       Decimal]) -> ComputationLedger`. Topologically
       evaluates computed casillas in order. Emits one
       `LedgerEntry` per computed casilla.
     - `audit_against(*, ruleset: Ruleset, provided:
       Mapping[str, Decimal], tolerance: Decimal =
       Decimal("0.01")) -> AuditReport`. Runs `derive` with
       user-supplied non-computed casilla values as inputs,
       then compares derived casillas against user-supplied
       derived values where both exist.
     - Internal `_evaluate_formula(formula: Formula,
       values: dict, parameters, period_start_date) ->
       Decimal`. Dispatches on `formula.op`; every operator
       has a concrete handler; `match` statement over
       `FormulaOp` is exhaustive.
     - Uses `decimal.localcontext(prec=28)` around each
       evaluation. No floats.
     - **Missing-input contract**: any non-computed casilla
       not present in `inputs` defaults to `Decimal("0")`.
       Rationale: Modelo 130 treats blank casillas as zero
       (AEAT Instrucciones). The engine logs one `debug`
       line per defaulted casilla for audit trail. A
       strict-mode flag (`Engine.derive(..., strict=True)`)
       is **not** added in wave 1 — adding later is
       additive.
- `Phase 4 — Modelo 130 rulesets`
  1. Create `src/aeat/domain/formulas/_rulesets/__init__.py` exposing
     `ALL_RULESETS: tuple[Ruleset, ...]`.
  2. Create `src/aeat/domain/formulas/_rulesets/_common.py` with
     helpers `build_casilla`, `add`, `sub`, `mul`, `percent`,
     `clamp_pos`, `max_op`, `min_op`, `brackets`, `round2`
     — concise factories returning the right pydantic union
     variant, so ruleset files read declaratively.
  3. Create `src/aeat/domain/formulas/_rulesets/modelo_130_2024.py`:
     - `RULESET: Ruleset` covering 2024-01-01 → 2024-12-31,
       mainland.
     - 19 casilla definitions (01–19) per research doc §Modelo
       130 per-casilla reference.
     - **9 formula definitions** for the single-period
       evaluator: `03, 04, 07, 09, 11, 12, 14, 17, 19` are
       computed.
     - User-input casillas: `01, 02, 06, 08, 10` (data
       entry), `05` (cross-quarter accumulator — supplied by
       caller, same treatment as `15`), `13` (minoración —
       supplied via the `compute_casilla_13` helper or direct
       entry), `15` (arrastre — supplied by caller), `16`
       (vivienda habitual — supplied by caller under
       eligibility gating), `18` (complementarias — usually
       0).
     - **Cross-quarter policy**: the engine evaluates one
       `FiscalPeriod` at a time. Casillas whose value depends
       on prior quarters (`05` pagos fraccionados anteriores
       and `15` arrastre) are **user-input** in this wave.
       The caller is responsible for maintaining the
       cross-quarter state; `Engine.audit_against` will flag
       a discrepancy if the caller mis-accumulates. A future
       wave may introduce a cross-period orchestration layer
       above the engine — NOT in scope here.
     - Parameter table with `irpf.trimestral_rate=0.20`,
       `agraria.trimestral_rate=0.02`, and the art 110.3.c
       brackets encoded inside a `BracketsFormula` referenced
       from the casilla-13 helper (casilla 13 is NOT
       computed — it is user-supplied; the engine ships a
       helper `compute_casilla_13(previous_year_rn: Decimal)
       -> Decimal` as a module-level convenience for callers
       without exposing a new operator. Placed in `_common.py`
       under this wave; may graduate to a dedicated helper
       later).
     - Legal citations: RIRPF art. 110.1.a, 110.1.b, 110.3.a,
       110.3.b, 110.3.c, 110.3.d, 110.4; LIRPF art. 99.
  4. Create `src/aeat/domain/formulas/_rulesets/modelo_130_2025.py`:
     Same shape; effective span 2025-01-01 → 2025-12-31.
     Formulas identical to 2024 (research doc §Mid-year rule
     changes).
  5. Register both rulesets in
     `_rulesets/__init__.py::ALL_RULESETS`.
- `Phase 5 — Public API`
  1. Fill `src/aeat/domain/formulas/__init__.py` with the full public
     re-export list (see ADR §10). Use explicit `__all__`.
  2. Add a `py.typed` marker inheritance verified (already
     present at `src/aeat/py.typed`).
- `Phase 6 — CLI`
  1. Create `src/aeat/domain/formulas/_cli.py` with Typer `app`:
     - `aeat formulas list` — JSON list of ruleset ids.
     - `aeat formulas show <ruleset_id>` — JSON of the full
       ruleset (casilla labels, parameters, formula ids).
     - `aeat formulas compute --modelo MODELO_130 --period
       2024Q2 --input 01=12000 --input 02=3500 ...` — runs
       `Engine.derive` and prints the ledger as JSON.
     - `aeat formulas audit --modelo MODELO_130 --period
       2024Q2 --provided 01=12000 --provided 03=8500 ...` —
       runs `Engine.audit_against` and prints the
       `AuditReport` as JSON.
  2. Create `src/aeat/entrypoints/cli/formulas.py` shim re-exporting the
     Typer app (mirrors `src/aeat/entrypoints/cli/modelos.py`).
  3. Wire into `src/aeat/entrypoints/cli/__init__.py`:
     `from . import formulas as formulas_module` +
     `app.add_typer(formulas_module.app, name="formulas",
     help="Per-modelo calculation formula engine (#173).")`.
- `Phase 7 — Unit tests (@pytest.mark.unit, colocated)`
  1. `src/aeat/domain/formulas/test_codes.py` — `FormulaOp` has
     exactly 13 members; values match member names lowercased;
     no duplicates. `Quarter` has 4 members.
  2. `src/aeat/domain/formulas/test_period.py` — `FiscalPeriod`
     start/end for every quarter of 2024 and 2025; `contains`
     for dates on the boundary; invalid year rejection.
  3. `src/aeat/domain/formulas/test_formula.py` — every pydantic
     operator subclass validates arity and operand type;
     floats rejected in `Literal`; string `"0.20"` coerces;
     nested operands round-trip through `model_dump_json` +
     `model_validate_json`.
  4. `src/aeat/domain/formulas/test_ruleset.py` —
     - happy path: the 2024 ruleset loads without error.
     - a synthetic ruleset with a dangling `CasillaRef`
       raises `CasillaNotDefinedError`.
     - a synthetic cyclic ruleset raises `FormulaCycleError`
       with the cycle reported.
     - a synthetic ruleset with a nested `ROUND` raises
       `RulesetValidationError`.
     - a synthetic ruleset referencing a missing `ParamRef`
       raises `RulesetValidationError`.
  5. `src/aeat/domain/formulas/test_registry.py` —
     - `get_registry()` returns a frozen registry containing
       exactly 2 rulesets (130.2024, 130.2025).
     - `resolve(MODELO_130, FiscalPeriod(year=2024,
       quarter=Q2))` returns 130.2024.
     - Overlap-rule: inserting a synthetic ruleset with
       overlapping span raises `AmbiguousPeriodError` at
       registry-assembly time.
     - `resolve` for a period with no matching ruleset
       raises `MissingRulesetError`.
     - registry binds exclusively to
       `aeat.domain.modelos.ModeloCode` (not the casillas-local
       restricted enum).
  6. `src/aeat/domain/formulas/test_engine.py` — the bulk:
     - **Q1 ordinary (Ap. I only, positive)**: inputs
       `{01: 12000, 02: 3500, 06: 500}` — user-input casillas
       `05, 08, 10, 13, 15, 16, 18` omitted, default to 0
       per the missing-input contract. Expected: `03=8500,
       04=1700.00, 07=1200.00, 11=0, 12=1200.00, 14=1200.00,
       17=1200.00, 19=1200.00` (assuming casilla 13=0 and
       15=0 and 16=0 and 18=0). Every casilla checked.
     - **Q1 loss (negative 03)**: `{01: 1000, 02: 3000}`.
       Expected: `03=-2000, 04=0 (clamp), 07=-500 (if 06=500),
       12=0 (floor), 14=0, 17=0, 19=0`.
     - **Arrastre across Q1→Q2 (caller-maintained)**:
       Q1 derives 19=-500. Q2 inputs include `15=500` and
       `05=<prior-quarter accumulator>`; the engine
       propagates both as user-inputs without deriving them.
       Test asserts the engine does NOT enforce `15 ≤ 14`
       (cap enforcement belongs to the caller); audit mode
       would flag a breach of the cap via a discrepancy
       against a synthetic reference computation if the
       caller builds one. Documented as a wave-2 candidate
       for cross-period orchestration.
     - **Casilla 13 sliding-scale helper (BRACKETS)**:
       previous-year RN = 8500 → 100; 9500 → 75; 10500 → 50;
       11500 → 25; 12500 → 0. Step function boundary tests
       at exact 9000 / 9000.01 / 10000 / 10000.01 / 11000 /
       11000.01 / 12000 / 12000.01.
     - **Combined apartados**: Ap.I positive, Ap.II negative
       — verifies cross-apartado offset in casilla 12.
     - **Both apartados → casilla 16 disallowed**: ruleset
       invariant tested via a caller helper; the engine itself
       does not enforce cross-casilla deduction-gating (left
       to the caller per ADR §casilla 16) — test documents
       the contract.
     - **Vivienda habitual cap (660,14 €)**: Ap.I only, base
       03=50000 → 2% raw = 1000 → capped to 660.14.
     - **Voluntary upscale**: an overridden
       `irpf.trimestral_rate=0.25` param in a custom ruleset
       computes 04 at 25% instead of 20%.
     - **Audit discrepancy**: user provides casilla 03=8499
       where the engine derives 03=8500 from 01=12000/02=3500
       — tolerance 0.01 → one `Discrepancy` emitted.
     - **Audit clean**: user provides casilla 03=8500 — no
       discrepancies.
     - **`AuditReport.assert_clean()`** raises when
       discrepancies present; does not raise when clean.
     - **Deterministic ledger order**: two derivations
       produce byte-identical ledgers.
     - **No floats accepted**: passing `{01: 12000.0}` is
       rejected by the input validator.
  7. `src/aeat/domain/formulas/test_cli.py` — JSON shape + exit
     code for every subcommand; invalid inputs raise the
     right error class; `aeat formulas audit` returns
     non-zero exit when `--strict` is set and discrepancies
     exist.
  8. `src/aeat/domain/formulas/test_smoke.py` — assert every public
     name in `aeat.domain.formulas.__all__` is importable.
  9. `src/aeat/domain/formulas/test_integration_modelos.py` —
     cross-checks that each ruleset's modelo is in
     `aeat.domain.modelos.MODELO_REGISTRY`. This closes the loop
     between the engine and the authoritative modelo
     catalogue.
- `Phase 8 — Linting + type-check`
  1. `just lint` must pass (ruff check + ruff format + relative-
     imports check).
  2. `just typecheck` must pass (ty strict mode).
  3. `just hooks` must pass on modified files.
- `Phase 9 — Commit cadence`
  Stage commits along phase boundaries, each a conventional
  commit:
  - `feat(errors): add FormulasError hierarchy (#173)`.
  - `feat(formulas): scaffold codes, period primitives (#173)`.
  - `feat(formulas): add casilla, formula, ruleset, registry models (#173)`.
  - `feat(formulas): add ledger + engine (#173)`.
  - `feat(formulas): codify Modelo 130 2024 + 2025 rulesets (#173)`.
  - `feat(formulas): wire CLI subcommands (#173)`.
  - `test(formulas): unit tests for engine + Modelo 130 (#173)`.

## Wave 2+ Backlog (deferred — NOT in this PR)

Each future wave is a complete vaultspec pipeline
(research ⇒ ADR ⇒ plan ⇒ execute ⇒ review ⇒ PR). Open as
separate issues when this wave lands:

- **Wave 2 — Modelo 303 (VAT quarterly)** — IVA devengado /
  soportado, prorrata, regularización anual. New operators
  may be needed: `RATIO`, `ACCUMULATED_SUM`. Canarias IGIC
  is out of scope (separate regime). Territorial overlays
  for Ceuta/Melilla and La Palma land here, with a dedicated
  overlay ADR.
- **Wave 3 — Modelo 100 (annual IRPF)** — the major annual
  return. Scope:
  - Amortization engine: linear and degressive methods per
    RIRPF art. 30; amortizable-asset registry cross-reference
    against deductible expenses (prevents double-count).
  - Property ownership: inmuebles urbanos arrendados,
    inmuebles urbanos no arrendados (imputación de rentas),
    amortization of rented properties.
  - Inventory valuation: FIFO, precio medio ponderado,
    precio específico — per RIRPF art. 68.
  - Progressive IRPF brackets (`BRACKETS` operator) — state
    + autonomic 2024 and 2025 tables. Autonomic bracket
    tables shipped as separate parameterised rulesets keyed
    by `autonomia` dimension.
  - Integration with the cumulative Modelo 130 ledger for
    the year (pagos fraccionados).
  - Mínimo personal y familiar calculation.
- **Wave 4 — Modelo 390 (annual VAT summary)** — rolls up
  the cumulative Modelo 303 ledger across the four quarters.
- **Wave 5 — Retenciones (111, 115, 123, 180, 190)** —
  autónomos with employees, rentals, or professional
  subcontractors. 180/190 as annual caps of 115/111.
- **Wave 6 — Informativas (347, 349, 720, 232)** — annual
  informational declarations. 720 has non-trivial
  amortization-adjacent valuation rules.
- **Wave 7 — Sociedades (200, 202)** — SL-side filings;
  deprioritised against the autónomo focus.
- **Wave 8 — Territorial overlays** — Ceuta/Melilla, La
  Palma, foral regimes (País Vasco, Navarra). Dedicated ADR
  for overlay mechanism before any implementation.

## Success Criteria

- `aeat.domain.formulas` subpackage exists with the exact public API
  declared in the ADR.
- Modelo 130 ruleset for 2024 and 2025 loads without error via
  `get_registry()`.
- `Engine.derive` produces the expected casilla values on every
  unit-test fixture.
- `Engine.audit_against` detects discrepancies at the 0.01 €
  tolerance and returns a clean report on matching inputs.
- `aeat formulas {list, show, compute, audit}` CLI subcommands
  return deterministic JSON and the right exit codes.
- `just lint`, `just typecheck`, and `just hooks` are green.
- Coverage on `src/aeat/domain/formulas/` is ≥ 90 % (the engine is
  pure-logic; full coverage is achievable).
- No new dependencies added to `pyproject.toml`
  (`graphlib`, `decimal`, `pydantic` v2 are all already
  present).
- `src/aeat/application/filing/_builders/modelo_130.py` continues to work
  unchanged (its swap is a follow-up issue).
- `corpus/casillas/` is NOT modified.
- The existing `aeat.domain.casillas.models.FormulaReference` stub
  continues to accept its legacy `expression: str` free-form
  field (no breaking change to the casilla catalogue).

## Risks & Mitigations

- **Risk**: Casilla 13's bracket function is implemented via
  the `BRACKETS` operator but is a *user-input* casilla in
  Modelo 130 (the taxpayer enters the amount; the engine does
  not compute 13 from 12's base). **Mitigation**: ship a
  module-level convenience helper
  `compute_casilla_13(previous_year_rn)` using a
  `BracketsFormula` node + parameter table, so the bracket
  machinery exercises the operator without pretending the
  engine derives casilla 13 in Modelo 130. Documented clearly
  in the helper's docstring.
- **Risk**: Cross-quarter arrastre (casilla 15 feeding from
  prior-quarter 19⁻) crosses a ruleset's evaluation boundary —
  the engine evaluates a single quarter at a time.
  **Mitigation**: the engine accepts the arrastre pool as an
  explicit input (`15` is a user-supplied casilla). The caller
  is responsible for maintaining the pool across quarters;
  the audit mode will flag discrepancies if the caller
  mis-computes the pool.
- **Risk**: `ModeloCode` collision between
  `aeat.domain.modelos._codes` (authoritative) and
  `aeat.domain.casillas.models` (restricted). **Mitigation**: the
  integration test `test_integration_modelos.py` asserts the
  ruleset registry binds to the authoritative enum only;
  ADR §8 documents the warning; `get_registry()` re-exports
  the authoritative symbol.
- **Risk**: Decimal arithmetic drift between `graphlib`-
  ordered evaluation and handwritten expected values in
  tests. **Mitigation**: every expected value in tests is
  hand-computed using `decimal.Decimal` literals (strings),
  quantized with `ROUND_HALF_UP`, mirroring the engine's
  presentation step. No floats ever in test expectations.
- **Risk**: La Palma / Ceuta-Melilla overlays deferred to
  wave 2 while AEAT already requires them for 4T 2025.
  **Mitigation**: the issue scope is explicitly wave-1; the
  ADR documents the La Palma requirement and stages it for
  wave 2; wave 1's mainland ruleset is self-consistent and
  safe for mainland users (the current autónomo user
  profile per `project_north_star` memory).

## Review Gates

- **Gate 1 — after Phase 2**: `Formula` / `Ruleset` load
  cleanly on a hand-written 2024 Modelo 130 ruleset
  (dry-run; no tests yet).
- **Gate 2 — after Phase 7**: all colocated unit tests pass
  locally.
- **Gate 3 — after Phase 8**: `just lint && just typecheck
  && just test` all green; 60 %+ coverage (project-wide
  floor) maintained.
- **Gate 4 — pre-PR**: `vaultspec-code-reviewer` agent
  review passes with no blocking issues.
