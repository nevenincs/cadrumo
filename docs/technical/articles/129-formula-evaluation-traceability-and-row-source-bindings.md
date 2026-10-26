# Formula evaluation, traceability, and row-source bindings

[Technical overview](../architecture.md) · [Article index](catalogue.md) · [Snapshot and reading guide](../reading-guide.md)

> This page describes the analyzed source snapshot. Its findings and limitations are not a certification of the current branch.

**Report:** `STAGE-2-129` · **Topic:** [Tax calculation domain](../topics/tax-calculation-domain.md)

<!-- preserved:article -->
## Scope and method

This chunk covers 14 registry-domain modules, 4,754 physical lines, 207,790 bytes, and 45,474 measured `o200k_base` proxy tokens. All nine bounded pages were read. The chunk includes the formula engine and Modelo 100 evaluators, governed-fact scoping, row-source bindings for inventory/invoices/IRNR, and their legal vocabularies. Static inspection only; no application code or tests were run, and no source was changed.

## Formula evaluation and traceability

`calculate_registry_snapshot` is the typed execution boundary for numeric, enum, date, boolean, relation and text channels. It canonicalizes casilla IDs, checks revision membership, applies separate text validation, defaults the filing date from the snapshot period or year end, merges relation values into binding values only when they agree, and rejects a binding supplied on both boolean and Decimal channels. Boolean facts remain booleans until used by an allowed predicate; date bindings are consumed through the age operation rather than as numeric leaves. The formula graph is evaluated in dependency order under a local Decimal precision of 28. `if_then_else` short-circuits the unselected branch. Snapshot evaluation entry point (`src/cadrumo/domain/calculations/registry/formula_runtime.py`) Formula result contract (`src/cadrumo/domain/calculations/registry/formula_runtime.py`) Evaluation context and dispatch (`src/cadrumo/domain/calculations/registry/formula_runtime.py`)

For each resolved formula target, the runtime applies declared rounding, checks casilla constraints, and records operand refs/values with legal and source provenance. Typed unresolved outcomes carry their own reason and provenance; unresolved dependencies propagate through downstream formulas without becoming numeric zero. The result refuses duplicate rows, a casilla that is both resolved and unresolved, and any observation/outcome without both legal and source refs. Its Decimal `values` and formula-only `entries` are derived views over canonical observations. These boundaries preserve the difference between an absent text value, a deferred dependency, and an actual zero. Per-target evaluation and unresolved outcomes (`src/cadrumo/domain/calculations/registry/formula_runtime.py`) Formula dispatch and conditional evaluation (`src/cadrumo/domain/calculations/registry/formula_runtime.py`)

Two local runtime validation gaps merit attention. `reject_non_decimal`, which is called for external Decimal channels, is currently a no-op (`del items, label`); Python callers can therefore pass values that violate the declared `Mapping[..., Decimal]` type and reach arithmetic without the promised boundary check. Separately, `Gasto193Observation._non_negative_gastos` is an ordinary private method, not a Pydantic validator, and nothing in this module calls it, so a negative amount is not refused when constructing this model. The gasto193 module also explicitly limits itself to selector/observation shape while a secure observation owner remains absent. Decimal guard implementation (`src/cadrumo/domain/calculations/registry/formula_runtime_ops.py`) Gasto193 observation model and selector contract (`src/cadrumo/domain/calculations/registry/gasto193_bindings.py`)

## Specialized tax operations and arithmetic helpers

The M100 cadastral imputed-rent operation reads the cadastral value, revised-value marker, disposal days, mixed-use flag/percentage/days and dated parameters. It rejects negative values, invalid checkbox text, missing no-cadastral substitute bases, days outside the parameterized 1–366 range, and inconsistent mixed-use data. When the registry row has no cadastral value but claims a positive imputation period, it refuses rather than fabricate a substitute base. The agricultural corrective-index evaluator applies the eight declared indices in sequence, skips nonpositive/blank index inputs as “not applied,” and leaves a nonpositive minorated result unchanged. M100 imputed-rent evaluator (`src/cadrumo/domain/calculations/registry/formula_runtime_m100.py`) M100 corrective-index cascade (`src/cadrumo/domain/calculations/registry/formula_runtime_m100.py`)

Shared operations cover arithmetic, comparisons, dated scalar parameters, bracket tables, keyed bracket tables and explicit rounding. Parameter resolution requires exactly one dated value; bracket selection rejects negative bases and requires coverage; keyed brackets return `None` only for absent parameter/key and refuse multiple matches. `integer-ceiling` uses ceiling toward positive infinity, with the current nonnegative target constraint called out in the implementation. A small consistency issue is that `reject_non_string` checks only truthiness, not `isinstance(value, str)`, despite its purpose and annotation; its safety therefore also relies on callers providing runtime-correct mappings. Parameter and bracket operations (`src/cadrumo/domain/calculations/registry/formula_runtime_ops.py`) Rounding and input gates (`src/cadrumo/domain/calculations/registry/formula_runtime_ops.py`)

## Authority scope and row-source capabilities

Governed fact validation runs under a context-local authority for the candidate generation being compiled. `CandidateFactAuthority` resolves from that candidate, caches queries with a bounded per-instance map, and carries an unpublished digest that is not confused with the published artifact. Projection caches use generation identity, weak ownership, locking and a size bound; absent explicit authority/scope refuses rather than reading an ambient published bundle. The relation handoff index separately records primary, alternate and formula consumption of each binding so an orphan handoff is visible. Candidate authority and cache (`src/cadrumo/domain/calculations/registry/governed_fact_scope.py`) Required authority scope (`src/cadrumo/domain/calculations/registry/governed_fact_scope.py`) Handoff consumer channels (`src/cadrumo/domain/calculations/registry/handoffs.py`)

The inventory selector defines three closed row operations and pins each to its semantic target casilla, with a target-relative year and activity projection grain. Its documentation clearly limits it to selector/build validation; source resolution, readiness and valuation are later integration work. Modelo 210 IRNR ledger bindings filter selected gross-income observations by target casilla and declared jurisdictions, aggregate exact Decimal amounts and expose a screen for nonzero observations no binding consumes. The latter returns unsupported observations rather than silently dropping them. Inventory operation contract (`src/cadrumo/domain/calculations/registry/inventory_bindings.py`) IRNR ledger selector (`src/cadrumo/domain/calculations/registry/irnr_ledger_bindings.py`)

Invoice observations provide typed counterparty, country, amount, date, operation claves and rectification coordinates. Family selectors close the fact/aggregation combinations, distinguish M347's clave vocabulary from M349's, filter rectification and regime scope, then aggregate party counts, taxable bases, gross totals or rectified-base deltas. Row bindings are grouped on source, grouping, rectification scope, claves and IVA regime; related bindings share one-based row indexes. M347 summary totals are calculated from threshold-filtered emitted type-2 rows. Its general threshold and the lower clave-C threshold are evaluated independently by party and clave bucket so qualifying a party under one floor cannot leak below-floor rows from the other. Invoice observation and selector contracts (`src/cadrumo/domain/calculations/registry/invoice_bindings.py`) Shared row cohorts and resolver (`src/cadrumo/domain/calculations/registry/invoice_bindings.py`) M347 threshold split (`src/cadrumo/domain/calculations/registry/invoice_bindings.py`) Invoice aggregates (`src/cadrumo/domain/calculations/registry/invoice_bindings.py`)

The dated invoice legal-classification catalogue supplies invoice classes and operation-date roles with legal references and semantically distinct pointers. Identifier evolutions make retirement or replacement explicit across editions, rather than treating omission as withdrawal. Anexo D applicability and foreign inventory bindings also resolve under explicit registry facts/selector contracts rather than hardcoding the filing year. Invoice legal-classification fact (`src/cadrumo/domain/calculations/registry/invoice_legal_classification.py`) Identifier evolution declarations (`src/cadrumo/domain/calculations/registry/identifier_evolutions.py`) Inventory applicability (`src/cadrumo/domain/calculations/registry/inventory_anexo_d_applicability.py`)

## Security, quality and limits

The engine avoids executing formulas as arbitrary code: operation names route through a closed evaluator set with arity checks, typed leaves, and registry-owned parameters. Its main risks are boundary regressions, missing legal facts, and incomplete source integration rather than code execution. The strongest follow-up is to restore concrete runtime value checks for external Decimal channels and promote the gasto193 nonnegative rule into an actual model validator before that observation surface is relied upon. Tests were not run, so these are static findings; the cross-model resolver and row materializer implementations are outside this chunk and are not assessed here.

## Coverage appendix

All 14 assigned files were read fully across nine bounded pages. Line counts are physical source lines.

- registry/formula_runtime.py (`src/cadrumo/domain/calculations/registry/formula_runtime.py`) — 1–1,310
- registry/formula_runtime_m100.py (`src/cadrumo/domain/calculations/registry/formula_runtime_m100.py`) — 1–407
- registry/formula_runtime_ops.py (`src/cadrumo/domain/calculations/registry/formula_runtime_ops.py`) — 1–590
- registry/formula_text_inputs.py (`src/cadrumo/domain/calculations/registry/formula_text_inputs.py`) — 1–112
- registry/gasto193_bindings.py (`src/cadrumo/domain/calculations/registry/gasto193_bindings.py`) — 1–111
- registry/governed_fact_scope.py (`src/cadrumo/domain/calculations/registry/governed_fact_scope.py`) — 1–193
- registry/handoffs.py (`src/cadrumo/domain/calculations/registry/handoffs.py`) — 1–89
- registry/identifier_evolutions.py (`src/cadrumo/domain/calculations/registry/identifier_evolutions.py`) — 1–68
- registry/ids.py (`src/cadrumo/domain/calculations/registry/ids.py`) — 1–67
- registry/inventory_anexo_d_applicability.py (`src/cadrumo/domain/calculations/registry/inventory_anexo_d_applicability.py`) — 1–46
- registry/inventory_bindings.py (`src/cadrumo/domain/calculations/registry/inventory_bindings.py`) — 1–117
- registry/invoice_bindings.py (`src/cadrumo/domain/calculations/registry/invoice_bindings.py`) — 1–1,049
- registry/invoice_legal_classification.py (`src/cadrumo/domain/calculations/registry/invoice_legal_classification.py`) — 1–371
- registry/irnr_ledger_bindings.py (`src/cadrumo/domain/calculations/registry/irnr_ledger_bindings.py`) — 1–224
<!-- /preserved:article -->
