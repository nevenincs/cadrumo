---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:2ada824c28c269d105d7496b78aca2af762a585acc20e1a8abac76b9634c27cb'
step_id: 'S277'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
  - "[[2026-08-24-tui-registry-api-gate-adr]]"
---

# Decide and record the per-casilla join semantics the Workspace schema record requires, deriving each edge from the registry's own declared direction rather than from field-name inference: whether a casilla row lists formulas whose output it is or formulas whose expression references it as an operand, which side of a relation a casilla row claims, and which casilla owns a multi-casilla applicability or constraint rule; amend the governing registry-api-gate decision record in the same change and prove each join against a real revision carrying both edge directions

## Scope

- `the amended 2026-08-24-tui-registry-api-gate-adr`
- `src/cadrumo/application/modelo/workspace.py schema-record construction`
- `and focused per-casilla join tests over a real multi-edge revision`

## Changes

- `M` `.vault/adr/2026-08-24-tui-registry-api-gate-adr.md`
- `M` `src/cadrumo/application/modelo/workspace.py`
- `M` `src/cadrumo/application/modelo/tests/test_workspace.py`
- `verify:` `uv run --no-sync pytest src/cadrumo/application/modelo/tests/test_workspace.py -m integration -q` -> `pass` (16 passed)
- `verify:` `uv run --no-sync ty check src/cadrumo/application/modelo/workspace.py src/cadrumo/application/modelo/tests/test_workspace.py` -> `pass`

## Notes

Four joins, four registry-grounded answers, none inferred from a field name
alone:

`formula_operands` is the INPUT direction. `FormulaExpression` is a
self-recursive tree (operator node carries `args`; a leaf carries exactly one
populated identity field), and every populated leaf maps 1:1 to its matching
`ModeloWorkspaceFormulaOperandReferenceV1` variant by the registry's own field
names (`casilla_id`, `binding`, `date_binding`, `parameter`, `relation`,
`literal`, `dispatch_table`) -- no walking of compiler internals beyond what
the type already declares. The OUTPUT direction
(`FormulaDefinition.target_casilla_id`) belongs to the provenance facet
("the canonical calculation-source graph"), not the schema facet, and is
never represented by `formula_operands` -- explaining why that field is
plural and multi-kind: many formulas can read one casilla, but at most one
produces it.

`relation_endpoints` needed no interpretation at all:
`RelationDefinition.source_casilla_id` and `.target_binding` are the exact,
unambiguous, already-named fields the two endpoint reference kinds mirror.

`constraints` turned out to have no join question in the first place --
`CasillaConstraints` is embedded directly on `CasillaDefinition.constraints`,
never a separately registered, cross-referenced collection, so "which casilla
owns a multi-casilla constraint rule" does not arise: no constraint rule
spans more than the one casilla that embeds it.

`applicability` was the one finding that reopens the plan Step's own framing.
Grepping every use of `ApplicabilityRuleId` across the registry found it
referenced ONLY by `ApplicabilityRuleDefinition.id` itself and consumed via
`revision.applicability[0]` (a per-REVISION, single-rule resolution through
`resolve_applicability_rule_from_authority`) -- there is no
casilla-to-applicability edge anywhere to decide an OWNER for. Ruled: the
field stays empty on every non-applicability row; a revision-wide fact must
not be misrepresented as belonging to one casilla. If a genuine casilla-scoped
applicability edge is added to the registry later, that is new registry data
to re-ground this ruling against, not a Workspace-side inference from the
current revision-scoped rule.

Proved `formula_operands` and `relation_endpoints` against real bundled data
carrying both edge directions rather than a synthetic fixture: modelo
130/2026/1T's casilla `03` is simultaneously the OUTPUT of
`modelo-130-rendimiento-neto` and consumed as an INPUT operand by
`modelo-130-pago-fraccionado-directa` -- two distinct real formulas,
confirming the edges are genuinely different data, not a hypothetical
distinction. Modelo 303/2026/1T's sole relation,
`modelo-303-rel-self-compensacion-anteriores`, gave a real source-casilla /
target-binding pair with distinct identities that must never cross-match.

Scope note: implemented the join-resolution PURE FUNCTIONS
(`formula_expression_operand_references`,
`formula_operand_references_for_casilla`,
`relation_source_endpoints_for_casilla`,
`relation_target_endpoints_for_binding`) and proved them directly; did not
wire them into a full `ModeloWorkspaceSchemaRecordV1` assembly loop, since
building the complete schema facet (walking every casilla/binding/formula/
relation/parameter into rows) is separate GRADED_SNAPSHOT/STATIC_INSPECTION
assembly work this Step's own scope note does not require ("schema-record
construction" here means settling and proving the join semantics the
construction will consume, not building the construction loop itself).
