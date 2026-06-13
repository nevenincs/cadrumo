---
tags:
  - '#exec'
  - '#registry-casilla-identity'
date: '2026-05-20'
modified: '2026-05-20'
step_id: 'S06'
related:
  - '[[2026-05-20-registry-casilla-identity-plan]]'
  - '[[2026-05-20-registry-casilla-identity-adr]]'
  - '[[2026-05-20-registry-casilla-identity-research]]'
---

# `registry-casilla-identity` `P02.S06`

Applied segment-aware casilla lookup to the runtime graph dependency
walk.

- Modified: `src/aeat/domain/calculations/registry/_runtime_graph.py`

## Description

`formula_evaluation_order` builds the computed-casilla dependency DAG by
matching the casilla reference tokens collected from each formula
expression (`expression_casilla_refs`) against the set of formula
`target`s. Both sides were compared as raw authored strings. Because
every authored casilla fragment sets `id == number`, a bare-number
formula leaf matched a bare-number target only as a side effect of that
convention; a multi-segment modelo whose formula targets a
segment-qualified `id` would lose the dependency edge from a bare-number
leaf.

A new helper `_casilla_reference_resolver` returns a token-to-canonical
map: every casilla `id` maps to itself, and a bare `number` that occurs
on exactly one casilla maps to that casilla's `id`. An ambiguous bare
number that recurs across record segments is omitted, so it can only be
named by the segment-qualified `id`. `formula_evaluation_order` resolves
both the formula `target` and every expression casilla reference through
this map before constructing the topological sort, so a multi-segment
bare-number reference is matched against the correct casilla occurrence.

`expression_casilla_refs` itself is unchanged: it still returns the raw
authored reference tokens, which is the contract its other consumer (the
formula-DAG validator in `_validate.py`) depends on. The segment-aware
resolution is confined to `formula_evaluation_order`, where tokens are
compared against targets.

Correctness for single-segment modelos is exact. Every casilla sets
`id == number`, so the resolver is the identity on every reference
token: `resolver.get(token, token)` returns the token unchanged for
every formula target and every expression leaf. The dependency graph,
the topological order, and the runtime evaluation sequence are
byte-identical to before.

## Tests

`uv run --no-sync pytest`: `test_runtime_graph.py` and
`test_formula_runtime.py` (23 passed), `test_modelo_parity_coverage.py`,
`test_modelo_100_registry.py`, `test_modelo_303_registry.py` (52
passed), `test_formula_modelo_registry_parity.py` (1 passed). The
runtime-graph dependency walk and formula evaluation order are exercised
across single-segment modelos with zero regression; all 26 modelos load
valid. `ruff check` on `_runtime_graph.py` clean.
