---
tags:
  - '#adr'
  - '#modelo-formulas'
date: '2026-04-17'
modified: '2026-06-13'
related:
  - '[[2026-04-17-modelo-formula-ruleset-research]]'
  - '[[2026-04-12-casilla-db-adr]]'
  - '[[2026-04-13-modelo-inventory-adr]]'
  - '[[2026-04-12-filing-draft-engine-adr]]'
  - '[[2026-04-12-base-module-structure-adr]]'
  - '[[2026-04-12-trilingual-i18n-adr]]'
  - '[[2026-04-17-relative-imports-adr]]'
---

# modelo-formulas adr: per-modelo calculation formula engine (**status:** `accepted`)

Date: 2026-04-17
Branch: `feature/173-modelo-formulas`
Issue: wgergely/aeat#173

## Status

Accepted (self-review, 2026-04-17). Executed end-to-end per the
vaultspec-system mandate; code review documented in the matching
exec summary.

## Problem Statement

Issue #173 asks for the programmatic rule engine that encodes the
mathematical relationships between AEAT casillas (boxes) for AEAT
modelos. The foundational milestone is **Modelo 130** (IRPF pago
fraccionado, estimación directa) — the quarterly filing that every
Spanish autónomo in estimación directa owes.

Today:

- `aeat.domain.casillas` ships a `FormulaReference` pydantic stub with a
  free-form `expression: str` field. The string is never parsed or
  executed; it is documentation-only.
- `aeat.application.filing._builders.modelo_130` ships a hard-coded Python
  computation of a synthetic 7-casilla Modelo 130, explicitly marked
  as a stand-in until #173 lands. The synthetic layout does not
  match the real AEAT Modelo 130 19-casilla form.
- There is no period-versioned ruleset registry: mid-year legal
  changes (e.g., the La Palma 60% pago-fraccionado reduction
  effective 2025-10-01) cannot be represented.
- There is no "reverse audit" capability: the system cannot detect
  discrepancies between a user-supplied casilla value and what the
  rules say it should be.

#173 must deliver:

1. A deterministic, sandboxed, period-aware **formula engine**
   (`aeat.domain.formulas`).
2. A codified **Modelo 130 ruleset** (19 casillas, 2024 and 2025
   periods) as the proof-of-concept.
3. **Forward (derive)** and **reverse (audit)** evaluation modes
   sharing the same ruleset + ledger format.
4. A clean integration surface for future waves (303, 100, 390,
   111, 115, 123, 347, 720 …).

## Considerations

- **Pydantic mandate** (from `CLAUDE.md`): every record must be a
  pydantic v2 model with `ConfigDict(strict=True, frozen=True)`.
  Formula nodes, rulesets, ledger entries, parameters — all
  pydantic. Zero bare dicts.
- **Trilingual contract**: every human-facing label inside a
  ruleset uses `Translatable`; Spanish authoritative for AEAT
  terminology.
- **No `eval`/`exec`/`compile`/`ast.parse`**: user-authored
  ruleset data must never reach Python's bytecode compiler.
  Formulas are structured pydantic trees with a closed operator
  enum.
- **Decimal discipline**: all monetary values are `Decimal`;
  ROUND_HALF_UP at the presentation step; intermediate precision
  4 decimal places; `Decimal` rates written as strings
  (`Decimal("0.20")`, never `0.2` float).
- **Period versioning** (OpenFisca pattern): rulesets are keyed by
  `(modelo, effective_from, effective_to)` with a territorial
  dimension for Ceuta/Melilla and La Palma. `RulesetRegistry.resolve`
  returns exactly one ruleset or raises `AmbiguousPeriodError`.
- **Double-accounting robustness**: the forward evaluation emits
  the same ledger shape that the reverse audit consumes. Every
  computed value records formula id, operator, operand refs,
  operand values, ruleset version, and result.
- **Relative-imports mandate** (#162): every internal import inside
  `src/aeat/domain/formulas/` must be relative (`from ._casilla import ...`
  or `from ..models import ...`). Absolute `aeat.*` imports allowed
  only in `tests/` and `scripts/`.
- **Public-API discipline**: external callers import from
  `aeat.domain.formulas` only. Internal modules are prefixed with `_`.
- **Testing mandate**: `@pytest.mark.unit` colocated next to each
  module. No mocks / patches / stubs — real pydantic instances and
  real `graphlib` invocations. Coverage contributes to the 60%
  floor.
- **Subpackage scope**: this ADR ships Modelo 130 (2024, 2025) as
  the proof-of-concept only. Modelo 303 / 100 / 390 / 111 / 115 /
  347 / 720 rulesets are explicitly deferred to future waves, each
  a standalone vaultspec pipeline.

## Decisions

### 1. Subpackage location and layout

A new public subpackage `aeat.domain.formulas` is created. Layout:

```
src/aeat/domain/formulas/
  __init__.py          # public API re-exports
  _codes.py            # FormulaOp StrEnum (ADD, SUB, MUL, DIV, MIN, MAX, IF,
                       #   BRACKETS, PERCENT, ROUND, LITERAL, CASILLA_REF,
                       #   PARAM_REF, CLAMP_POSITIVE)
  _casilla.py          # CasillaDefinition (strict pydantic v2)
  _formula.py          # Formula pydantic model, discriminated union by op
  _period.py           # FiscalPeriod (pydantic): year, quarter, effective date span
  _ruleset.py          # Ruleset, ParameterTable, ParameterValue (date-keyed)
  _registry.py         # RulesetRegistry.resolve(modelo, period, territory)
  _ledger.py           # ComputationLedger, LedgerEntry, Discrepancy
  _engine.py           # Engine.derive / Engine.audit_against
  _errors.py           # FormulasError hierarchy under aeat.core.errors.AeatError
  _rulesets/           # concrete ruleset modules
    __init__.py
    _common.py         # shared helpers (build_ruleset, param_table, ...)
    modelo_130_2024.py
    modelo_130_2025.py
  _cli.py              # aeat formulas list / show / compute / audit
  test_*.py            # colocated @pytest.mark.unit tests (Rust-style)
```

Rationale: follows the existing subpackage precedent
(`aeat.domain.casillas`, `aeat.domain.modelos`, `aeat.domain.portals`). Keeps the public
import surface clean (`from aeat.domain.formulas import Engine`) and avoids
any collision with the issue-#9 `aeat.domain.schema` namespace that may
land later — #173 owns `aeat.domain.formulas`, #9 owns `aeat.domain.schema`.

### 2. Formula representation — pydantic-graph DSL (no parser)

Every formula is a pydantic v2 model with a closed `FormulaOp`
enum and a typed `operands` tuple. No string-to-code compilation.
No `ast.parse`. No `eval`. No `exec`.

```python
class FormulaOp(StrEnum):
    LITERAL = "literal"           # a Decimal constant
    CASILLA_REF = "casilla_ref"   # value of another casilla
    PARAM_REF = "param_ref"       # value of a named ruleset parameter
    ADD = "add"                   # n-ary
    SUB = "sub"                   # binary
    MUL = "mul"                   # n-ary
    DIV = "div"                   # binary, with explicit quantize
    MIN = "min"                   # n-ary
    MAX = "max"                   # n-ary
    CLAMP_POSITIVE = "clamp_pos"  # unary: max(0, x)
    PERCENT = "percent"           # binary: rate × base (Decimal)
    BRACKETS = "brackets"         # stepwise function over brackets (for casilla-13)
    ROUND = "round"               # unary: quantize to 2dp + ROUND_HALF_UP
```

**Operator-surface scope discipline.** The wave-1 operator set is
the minimum that covers the Modelo 130 DAG (§research doc §Full
casilla DAG). Operators that are *not* required by Modelo 130
(e.g., `IF`, `EQ`, `LTE`, `RATIO`, `ACCUMULATED_SUM`) are
deliberately **omitted**. They will be added in a future wave,
behind a new ADR, when a concrete Modelo-ruleset citation
justifies them. The rationale is that each operator expands the
engine's attack and audit surface; keep the set minimal and
auditable.

Every `Formula` is a **discriminated union by `op`**: pydantic
validates the shape of `operands` per operator at load time.
`AddFormula(op=ADD, operands=tuple[Operand, ...])` accepts any
number of operands; `SubFormula(op=SUB, operands=tuple[Operand,
Operand])` enforces arity 2; `IfFormula(op=IF, operands=tuple[
Operand, Operand, Operand])` enforces arity 3; etc.

`Operand` is itself a discriminated union: `Literal | CasillaRef |
ParamRef | Formula`. Recursive — formulas nest arbitrarily deep.

`CasillaDefinition` ships human-facing labels via the
`Translatable` TypedDict from `aeat.core.i18n` (trilingual contract):

```python
class CasillaDefinition(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    casilla_id: str
    label: Translatable          # es (authoritative), en, hu
    computed: bool
    data_type: CasillaDataType   # from aeat.domain.casillas
    legal_basis: tuple[LegalCitation, ...]
```

**Rationale**: matches the pydantic-v2 mandate. Eliminates the
eval attack vector entirely. Free schema validation at load time.
Easy to serialise to/from JSON / YAML. Plays natively with
`graphlib.TopologicalSorter`. Chosen over `asteval` (float-centric,
too powerful), `simpleeval` (unnecessary attack surface), and
AST-whitelist (Python-version maintenance burden).

A sealed `SafeExprFormula` operator is **explicitly rejected** for
this wave. If a Modelo rule ever proves too clumsy in the pure
DSL, a future ADR may introduce it behind a non-default feature
flag.

### 3. Period versioning — OpenFisca-style date-keyed rulesets

```python
class Ruleset(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    ruleset_id: str                 # e.g. "modelo_130.2024"
    modelo: ModeloCode              # from aeat.domain.modelos._codes (authoritative)
    effective_from: date
    effective_to: date | None       # None = open-ended
    casillas: tuple[CasillaDefinition, ...]
    formulas: tuple[FormulaDefinition, ...]
    parameters: ParameterTable
    legal_citations: tuple[LegalCitation, ...]
```

- `FiscalPeriod` is a pydantic model with `year: int` (1990–2100)
  and `quarter: Quarter | None` (enum: Q1..Q4). It resolves to a
  `(start, end)` date span used by the registry.
- A `ParameterTable` is a `Mapping[str, tuple[ParameterValue,
  ...]]` where each `ParameterValue` carries
  `(effective_from, effective_to, value: Decimal)`. Matches
  OpenFisca verbatim.
- `RulesetRegistry` indexes rulesets by modelo.
  `resolve(modelo, period)` returns the one ruleset whose span
  covers the period, or raises `AmbiguousPeriodError` if a period
  straddles a rule change.
- **Territorial overrides are explicitly deferred** to wave 2+.
  Wave 1 ships mainland rulesets only. `Ruleset` does not carry a
  `Territory` field in wave 1 — the overlay mechanism is designed
  against real requirements when the La Palma / Ceuta-Melilla
  research lands. Adding a field later is additive; carrying a
  speculative field today is dead public surface.

Modelo 130 ships two rulesets initially:

- `modelo_130.2024.mainland` covering 2024-01-01 through 2024-12-31.
- `modelo_130.2025.mainland` covering 2025-01-01 through 2025-12-31
  (open-ended; superseded when 2026 legislation lands).

Both rulesets share identical formulas (see research doc §Mid-year
rule changes — no mechanical changes between 2024 and 2025). The
separate ruleset files make it trivial to diverge later.

### 4. DAG evaluation — `graphlib.TopologicalSorter`

Python's stdlib `graphlib.TopologicalSorter` is the evaluator's
core. No `networkx` dependency.

- At ruleset load time: build a full DAG of all computed casillas
  keyed by `CasillaRef`, call `ts.prepare()` to detect cycles.
  Cycles raise `FormulaCycleError` carrying the cycle and the
  ruleset id.
- At evaluation time: `ts.static_order()` yields the iteration
  order. Each iteration evaluates one formula, appends a
  `LedgerEntry`, and stores the result in the values dict.
- All ordering is deterministic across runs — pydantic preserves
  field order and `graphlib` uses insertion order.

### 5. Decimal arithmetic

- All values are `Decimal`. `Literal` fields are
  `Annotated[Decimal, BeforeValidator(_coerce_str_to_decimal)]`
  — YAML/JSON strings are coerced; floats are **rejected**
  (strict=True).
- Intermediate precision: 4 decimal places.
- Published outputs: `ROUND` node quantizes to 2 decimal places
  with `ROUND_HALF_UP`.
- `DIV` operator requires an explicit `quantize` field; division
  never emits unbounded repeating decimals.
- A global `decimal.localcontext(prec=28)` is set by the engine
  before each computation and reset afterwards.
- **Single-rounding invariant:** intermediate operator nodes
  (`ADD`, `SUB`, `MUL`, `PERCENT`, `MIN`, `MAX`, `CLAMP_POSITIVE`,
  `BRACKETS`) **never round**. `DIV` carries an explicit
  `quantize` field at 4 decimal places (preventing unbounded
  repeating decimals) and is still considered intermediate.
  Each published (declared) casilla has **exactly one** terminal
  `ROUND` node quantising to 2 decimal places with
  `ROUND_HALF_UP`. Nested `ROUND` nodes are rejected at ruleset
  load time to prevent double-rounding.

### 6. Forward + reverse evaluation

Two public methods on `Engine`:

```python
class Engine:
    def derive(
        self,
        *,
        ruleset: Ruleset,
        inputs: Mapping[str, Decimal],
    ) -> ComputationLedger:
        """Evaluate all computed casillas from user-supplied inputs."""

    def audit_against(
        self,
        *,
        ruleset: Ruleset,
        provided: Mapping[str, Decimal],
        tolerance: Decimal = Decimal("0.01"),
    ) -> AuditReport:
        """Recompute and compare against user-supplied values."""
```

- `derive` does a topological sort of computed casillas, evaluates
  each formula, and emits a `ComputationLedger` (tuple of
  `LedgerEntry`).
- `audit_against` accepts a full value set (including values the
  rules say are derivable) and returns an `AuditReport`: the
  ledger plus a tuple of `Discrepancy` records where the provided
  value differs from the derived value by more than the tolerance.
- Both modes share the same `LedgerEntry` shape:

  ```python
  class LedgerEntry(BaseModel):
      model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

      casilla_id: str                     # e.g. "03"
      value: Decimal                       # computed (rounded) result
      op: FormulaOp                        # terminal operator for the node
      formula_id: str                      # stable id for audit linkage
      operand_refs: tuple[str, ...]         # casilla / param references
      operand_values: tuple[Decimal, ...]   # materialised operand values
      ruleset_id: str                      # e.g. "modelo_130.2024"
      notes: str = ""                      # engine-emitted trace note
  ```

- Tolerance defaults to 1 cent (`Decimal("0.01")`), matching the
  presentation rounding precision.
- Logging uses `aeat.core.logging.get_logger(__name__)` on every
  module under `aeat.domain.formulas` (per project mandate). The engine
  logs one `info` line per ruleset evaluation (ruleset id +
  casilla count) and `debug` lines per ledger entry; no `print`
  calls anywhere.

### 7. Error hierarchy

All formula errors inherit from `aeat.core.errors.AeatError` via an
intermediate `FormulasError`:

```
AeatError
  └── FormulasError
        ├── RulesetValidationError     # at load time
        ├── FormulaCycleError
        ├── CasillaNotDefinedError
        ├── AmbiguousPeriodError
        ├── MissingRulesetError
        ├── EvaluationError            # runtime division-by-zero etc.
        └── AuditDiscrepancyError       # raised when strict=True
```

`Engine.audit_against` does not raise on discrepancy by default —
it returns an `AuditReport`. Callers may invoke `report.assert_clean()`
to raise `AuditDiscrepancyError` when they want a strict guard.

### 8. Integration with existing subpackages

- **`aeat.domain.casillas.FormulaReference` stub**: deprecated in-place.
  The existing `CasillaRecord.formula: FormulaReference | None`
  slot accepts the old `expression: str` free-form field; we do
  NOT modify `aeat.domain.casillas.models` in this wave (it would be a
  breaking change beyond #173 scope). Instead, `aeat.domain.formulas`
  declares its own canonical `FormulaDefinition`, and the
  `aeat.domain.casillas` stub remains for documentation of the casilla
  catalogue's intent until a future wave re-plumbs the catalogue
  onto `aeat.domain.formulas`.
- **`aeat.domain.modelos.ModeloCode`**: referenced as the single source of
  truth for modelo identifiers. Rulesets bind to `ModeloCode`.
  **Naming-collision warning:** `aeat.domain.casillas.models.ModeloCode`
  is a *different* symbol (a restricted enum containing only
  `MODELO_130 / 303 / 390` for the casilla corpus). Ruleset
  authors MUST import `from ..models import ModeloCode` (the
  authoritative registry), NOT from `aeat.domain.casillas.models`. A
  test asserts the ruleset registry binds exclusively to
  `aeat.domain.modelos.ModeloCode`.
- **`aeat.application.filing._builders.modelo_130`**: NOT modified in this
  wave. The existing synthetic builder continues to satisfy its
  tests; replacing it with a ruleset-driven equivalent is a
  downstream integration step covered by a follow-up issue and
  plan. Scope-protection: #173 asks for the engine + Modelo 130
  ruleset; it does not ask for the filing-builder rewrite.
- **`aeat.domain.portals`**, **`aeat.domain.deadlines`**: not touched.
- **`aeat.entrypoints.cli`**: new `aeat formulas` subcommand wired in.

### 9. Sandboxing / supply-chain hygiene

- No operator accepts a raw string expression.
- All `Literal` values are coerced `Decimal(str_value)`; floats
  rejected.
- `BRACKETS` payloads are typed pydantic records (no open ranges
  expressed as strings).
- `graphlib.TopologicalSorter` is the only evaluation primitive.
- No dependency on `asteval` / `simpleeval` / `sympy`.
- No YAML loader used in wave 1 — rulesets ship as Python
  modules under `_rulesets/`. YAML/JSON ingestion lands in a
  future wave under a dedicated secure-loader ADR.

### 10. Public API surface

From `aeat.domain.formulas`:

- `Engine`, `ComputationLedger`, `LedgerEntry`, `Discrepancy`,
  `AuditReport`
- `Ruleset`, `RulesetRegistry`, `get_registry`
- `FormulaOp`, `Formula`, `Literal`, `CasillaRef`, `ParamRef`,
  `CasillaDefinition`, `FormulaDefinition`
- `FiscalPeriod`, `Quarter`, `ParameterTable`, `ParameterValue`
- Error classes: `FormulasError`, `RulesetValidationError`,
  `FormulaCycleError`, `CasillaNotDefinedError`,
  `AmbiguousPeriodError`, `MissingRulesetError`,
  `EvaluationError`, `AuditDiscrepancyError`

All underscored modules are implementation-private.

## Consequences

- Wave 1 ships a complete Modelo 130 ruleset (19 casillas) for
  2024 and 2025. Forward and reverse evaluation pass deterministic
  test fixtures covering: ordinary positive quarter, all-zero
  quarter, negative 03 floors 04 at 0, negative 07 propagating
  through the cross-quarter arrastre, casilla-13 sliding scale
  (all five tiers), casilla-16 vivienda-habitual cap (660,14 €
  hard cap), casilla-16 disallowed when both apartados operate,
  audit discrepancy detection, cycle detection on a synthetic
  malformed ruleset, period ambiguity detection on a constructed
  overlap.
- The existing synthetic `Modelo130Builder` in
  `aeat.application.filing._builders` is NOT modified; its swap to the new
  engine is a follow-up issue.
- Future waves (Modelo 303, 100, 390, ...) reuse the same engine
  without modifying it: each wave adds new rulesets under
  `_rulesets/` and, if needed, new operators in `_codes.py`.
- The La Palma 60% reduction and Ceuta/Melilla variants are
  plumbed via `Territory` but NOT exercised in wave 1 — they land
  in wave 2 with their own overlays, tests, and legal-citation
  review.
- The FormulaReference stub in `aeat.domain.casillas.models` remains; a
  future wave will re-plumb the casilla catalogue onto
  `aeat.domain.formulas`. No breakage in wave 1.

## Wave plan (out of scope for this PR; tracked as follow-up)

Each future wave is a complete vaultspec pipeline (research ⇒ ADR
⇒ plan ⇒ execute ⇒ review ⇒ PR). Listed here so reviewers see
the trajectory:

- **Wave 2 — Modelo 303 (VAT quarterly)**: IVA devengado vs.
  soportado, prorrata, regularización anual. New operators if
  needed: `RATIO`, `ACCUMULATED_SUM`. Territorial overlays for
  Canarias IGIC (separate regime — documented but explicitly out
  of scope for AEAT Modelo 303).
- **Wave 3 — Modelo 100 (annual IRPF)**: the major annual return.
  Brings in amortization tables (linear / degressive methods per
  RIRPF art. 30), property ownership (casillas for inmuebles
  urbanos, tanto arrendados como no arrendados), inventory
  valuation, cross-reference against the amortizable-asset
  registry vs. deductible expenses (prevents double-counting
  between amortization and gasto deducible). Progressive IRPF
  brackets via the `BRACKETS` operator (state + autonomic, 2024
  and 2025 tables). Integrates the cumulative Modelo 130 pagos
  fraccionados.
- **Wave 4 — Modelo 390 (annual VAT summary)**: rolls up the
  cumulative Modelo 303 ledger.
- **Wave 5 — Retenciones modelos (111, 115, 123, 180, 190)**.
- **Wave 6 — Informativas (347, 349, 720, 232)**.
- **Wave 7 — Sociedades (200, 202)** (low priority; autónomo
  focus).
- **Wave 8 — Territorial overlays (Ceuta/Melilla, La Palma, foral
  regimes).**

Each wave carries its own AEAT-primary source audit, legal-
citation table, and plan.

## Alternatives Considered

- **asteval** — rejected. Float-first, too powerful (loops,
  comprehensions, user-defined functions are all attack surface),
  maintainers explicitly decline to guarantee safety.
- **simpleeval** — rejected. Would add a dependency for an
  expression layer we do not need once the pydantic DSL is in
  place. Operator coercion can silently demote `Decimal` to
  `float`.
- **sympy** — rejected for evaluation. Massive dependency, wrong
  problem shape, `sympify` has historical eval footguns. Kept
  as a potential offline property-testing sidecar (future).
- **AST-whitelist** — rejected as primary. Odoo's `safe_eval`
  history shows that maintaining an AST whitelist across Python
  versions is an ongoing CVE surface.
- **YAML-backed rulesets (load-at-runtime)** — rejected for wave
  1. Python modules are auditable via git diff, typed by MyPy,
  and executable by the same interpreter that runs the tests.
  YAML ingestion lands later behind a dedicated secure-loader
  ADR.
- **Modelo 303 or 100 as the wave-1 proof-of-concept** — rejected.
  130 is the smallest well-specified modelo with the full DAG
  surface (percentage, subtraction, stepwise minoración, cross-
  quarter carry, min/max/clamp, cap, disallowance rule). It
  exercises every planned operator.
