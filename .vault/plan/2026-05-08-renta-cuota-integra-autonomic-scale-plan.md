---
tags:
  - '#plan'
  - '#renta-cuota-integra-autonomic-scale'
date: '2026-05-08'
modified: '2026-05-08'
related:
  - "[[2026-05-08-renta-cuota-integra-autonomic-scale-adr]]"
  - "[[2026-05-08-renta-cuota-integra-autonomic-scale-research]]"
---
# `renta-cuota-integra-autonomic-scale` plan

Implementation plan grounded in the
`renta-cuota-integra-autonomic-scale-adr` decision: extend the
runtime with a `lookup_bracket_by_ccaa` op, then wire 90 per-CCAA
bracket-table parameters and 12 per-revision formulas (2 casillas × 6
ejercicios) so the autonomic IRPF cuota integra computes end-to-end
from the operator's tax-residence CCAA's progressive scale.

## Proposed Changes

Three layers, sequenced strictly per the ADR:

1. **Runtime extension** — a single Python change to
   `aeat.domain.calculations.registry._formula_runtime` introducing
   the `lookup_bracket_by_ccaa` op + the `dispatch_table` leaf type.
   Includes schema-side support in
   `aeat.domain.calculations.registry._schema.FormulaExpression`,
   updates to `_evaluate_leaf` for string-typed bindings, plus
   targeted unit tests for the new op (synthetic CCAA dispatch
   against a fixture bracket table).

2. **Per-CCAA bracket-table parameters** — one parameter per CCAA
   per ejercicio, with the bracket schedule sourced from the
   relevant per-jurisdiction legal authority and pinned via
   `legal_refs` and `source_refs`.

3. **Per-revision formulas at 0529 / 0531** — the dispatch formulas
   that consume the per-CCAA parameters via the new runtime op.
   Construct ownership lists are updated to include the new formula
   ids, and the orphan-detection allow-list is extended /
   contracted as each CCAA's data lands.

The proof CCAA is **Madrid 2025**: well-documented, AEAT-cited, and
small enough to validate the design end-to-end before fanning out.

## Tasks

- Phase 1 — Runtime extension
  1. Step 1.1 — Extend `FormulaExpression` schema with a
     `dispatch_table` leaf field (mapping `str` -> `str`).
  1. Step 1.2 — Allow string-typed values in `_evaluate_leaf` for
     bindings whose backing profile field is a `StrEnum`.
  1. Step 1.3 — Implement `op = "lookup_bracket_by_ccaa"` in
     `_evaluate_expression`. Use `_resolve_bracket` for the
     dispatched parameter.
  1. Step 1.4 — Add unit tests covering: happy-path dispatch against
     a known CCAA; missing CCAA in the dispatch table raises
     `RegistryValidationError`; non-bracket-table parameter raises
     `RegistryValidationError`.
  1. Step 1.5 — Commit + push the runtime extension as a single
     focused commit citing this plan.

- Phase 2 — Madrid 2025 proof slice
  1. Step 2.1 — Source the Madrid 2025 autonomic scale from the
     relevant Madrid BOCM publication; verify against AEAT manual
     práctico parte 1 (`aeat-renta-2025-manual-parte1`).
  1. Step 2.2 — Add the parameter
     `renta-2025-escala-autonomica-madrid-base-general` to
     `registry/aeat/modelos/100/revisions/2025.toml` with the
     sourced bracket data and citations.
  1. Step 2.3 — Add the two casilla formulas
     (`renta-2025-cuota-escala-autonomica-sobre-base-liquidable-general`
     and `renta-2025-cuota-escala-autonomica-sobre-minimo-personal-familiar`)
     using `lookup_bracket_by_ccaa` with a single-entry dispatch
     table for Madrid only. Other CCAA values must error until they
     are wired.
  1. Step 2.4 — Add the two formula ids to the construct's
     `formulas = [...]` list in revision 2025.
  1. Step 2.5 — Add a registry calculation scenario that drives a
     synthetic Madrid-resident profile through the autonomic cuota
     chain and asserts the cuota matches the AEAT manual's worked
     example. Use the workbook-parity gate as the cent-level
     contract.
  1. Step 2.6 — Commit + push the Madrid 2025 slice as a single
     focused commit.

- Phase 3 — Fan out per CCAA for 2025
  Repeat phase-2 steps for each of the remaining 14 CCAA in 2025,
  one CCAA per commit. Each commit:
   - sources the per-CCAA scale from the relevant per-jurisdiction
     authority;
   - adds the parameter declaration with citations;
   - extends the dispatch_table on the two existing 2025 formulas
     to include the new CCAA;
   - adds a registry calculation scenario for the CCAA;
   - confirms drift-detection and parity gates stay green.

  When all 15 CCAA are wired, casillas 0529 and 0531 are fully
  computed for 2025.

- Phase 4-8 — Backport per ejercicio
  Repeat phase-2 + phase-3 for ejercicios 2024, 2023, 2022, 2021,
  2020 in order. Each ejercicio is a single phase with 15 sub-tasks
  (one per CCAA). Ejercicios touch their respective per-year toml.

- Phase 9 — Closure verification
  1. Step 9.1 — Confirm `_PRE_STAGED_PARAMETERS` carries no
     autonomic-scale entries (every per-CCAA per-year parameter is
     consumed by a formula).
  1. Step 9.2 — Run the full registry suite and the live-AEAT
     replay against Renta WEB Open. Verify casillas 0529, 0531,
     0533, 0546 across the supported ejercicios for each CCAA.
  1. Step 9.3 — Update the audit-concerns plan to mark this stream
     closed.

## Parallelization

Phase 1 (runtime extension) is a strict prerequisite for every
following phase — must land first and stay green.

Within phase 3 (and the per-ejercicio fan-outs in phases 4-8), the
15 CCAA tasks are independent — each touches a distinct parameter
declaration and adds one entry to a shared dispatch_table. Multiple
agents can land per-CCAA commits in parallel as long as each commit
keeps the dispatch_table self-consistent (the formula's
dispatch_table and the parameter's per-CCAA id stay in sync).

Per-ejercicio phases (4-8) are independent of each other and can
land in any order after phase 3. The plan sequences them
year-descending only because authoritative data is freshest for
recent ejercicios.

## Verification

Mission success is measured by all of:

1. The runtime extension's targeted unit tests pass (happy path,
   missing-CCAA error path, wrong-parameter-type error path).
2. `test_no_orphan_parameters_in_any_revision` passes with no
   autonomic-scale entries in `_PRE_STAGED_PARAMETERS`. The
   dispatch_table leaf counts as a parameter reference.
3. `test_every_formula_parameter_reference_resolves_to_a_declared_parameter`
   passes for every ejercicio across every CCAA.
4. Per-CCAA scenario tests assert the autonomic cuota matches the
   AEAT manual's worked example or the live-oracle replay for that
   CCAA × ejercicio.
5. Workbook parity tests confirm the dispatch op produces the same
   bracket arithmetic as AEAT's published workbook for every CCAA.

The autonomic chain is correct end-to-end when those five gates
hold simultaneously across all 15 × 6 = 90 (CCAA × ejercicio)
combinations. Tests cannot be cheated because (1) the bracket data
is committed and per-CCAA reviewable, (2) the cuota arithmetic is
exercised against AEAT's own outputs, and (3) the dispatch
mechanism rejects any CCAA value that is not in the dispatch table —
forcing every supported jurisdiction to be wired explicitly.

## Status (2026-05-12)

All nine phases of the original scope are closed. Every 15 × 6 = 90
CCAA × ejercicio combination is wired in the committed registry,
verified against AEAT manual práctico parte 1 and the relevant
regional gazette, and exercised by the orphan-detection sweep plus
the structural-rejection gates.

Phase closure summary:

- **Phase 1 (Runtime extension)** — `lookup_bracket_by_ccaa` op and
  `dispatch_table` leaf landed in `_schema.py` / `_formula_runtime.py`;
  five focused unit tests in `test_lookup_bracket_by_ccaa.py` cover
  the happy path, missing-CCAA error, wrong-parameter-type error,
  and unset-binding error.
- **Phase 2 (Madrid 2025 proof slice)** — Madrid 2025 scale committed
  with five-bracket schedule sourced from BOCM and cross-checked
  against AEAT manual práctico.
- **Phase 3 (Fan-out 2025)** — remaining 14 CCAA wired into 2025.
- **Phases 4-8 (Backport 2024 / 2023 / 2022 / 2021 / 2020)** — each
  ejercicio carries 15 per-CCAA bracket parameters plus the 0529 /
  0531 dispatch formulas. Bracket data hand-cross-checked between
  the AEAT manual práctico for that ejercicio and the relevant
  Decreto Legislativo / Decreto-Ley from each regional gazette.
- **Phase 9 (Closure)** — `_PRE_STAGED_PARAMETERS` carries no
  autonomic-scale entries; the drift-detection sweep confirms every
  per-CCAA parameter is consumed via the dispatch leaf.

### Post-execution hardening (audit-discovered)

The autonomic-scale wave surfaced several adjacent gaps that landed
as focused follow-up commits, tracked in the session task ledger:

- **#41** — SQL `secure_objects` records enrolled into pydantic v2
  strict models.
- **#42** — calculation-pipeline test coverage gaps audit.
- **#43** — `verification_expectations` blocks declared across modelos
  100 / 200 / 202 / 303 / 309 / 322 / 353 / 369 (×3 schemes) / 390.
- **#45** — deferred `enum_binding_values` fix landed in
  `test_ledger_renta_expense_binding`.
- **#47** — atribución de rentas pass-through rate wired into the
  Modelo 184 cross-modelo formula.
- **#48** — unresolved merge-conflict markers in
  `test_error_boundary_integration.py` resolved.
- **#49** — orphan-detection leaf walkers consolidated into
  `_runtime_graph` public helpers (`expression_binding_refs`,
  `expression_parameter_refs`). Closed a latent dispatch_table-
  undercounting bug in `_queries.py:ModeloFormulaRow.input_parameters`
  for every autonomic-scale formula.
- **#50** — structural rejection test in `test_registry_schema.py`
  pinning the validator's dispatch_table parameter-resolution gate.
- **#51** — six unit tests in `test_text.py` covering
  `normalise_corpus_text` after the math-notation regex fix.
- **#52** — eight unit tests in `test_runtime_graph.py` pinning the
  public `expression_*_refs` walkers, with explicit regression
  coverage for the dispatch_table walking case.

### Out-of-scope follow-ups (not blocking closure)

- **#44 (data-blocked)** — Modelo 100 chain-behaviour scenario
  expansion needs AEAT-published worked-example oracle data per
  CCAA × ejercicio. The no-tautological-calculation-tests rule
  forbids hand-computed expected values, so this task waits on
  external oracle data.
- **#46 (vaultspec-gated)** — wiring orphan RIC parameters
  (`renta-2025-ric-reduccion-rate-maximo`,
  `renta-2025-ric-materializacion-plazo-anos`,
  `renta-2025-ric-mantenimiento-plazo-anos`) into the Modelo 100
  RIC reduction chain needs a research → ADR → plan pass for the
  26-casilla RIC scope before code lands.
