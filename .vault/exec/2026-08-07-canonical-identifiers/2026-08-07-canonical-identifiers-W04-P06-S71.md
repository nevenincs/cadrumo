---
tags:
  - '#exec'
  - '#canonical-identifiers'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:4d73bfbeec84f1b263bfd228c91b1e5ab9dd593f3a668f17ce3415bedfac8d5d'
step_id: 'S71'
related:
  - "[[2026-08-07-canonical-identifiers-plan]]"
---

# scope `bucket_id`'s real 81-site population — report only, do not open

## Scope

- `src/cadrumo/entrypoints/`
- `src/cadrumo/application/`

## Description

- This row's own gate is the scoping report itself, not a retype — no
  code was touched, per the team lead's explicit "do not open the work."
- Re-confirmed the `W04.P06.S31` measurement rather than re-deriving from
  scratch (the tree-wide AST probe was already run there): 81 bare
  `bucket_id` pydantic model fields, `entrypoints` 55, `application` 20,
  `llm` 2, `core` 1, `domain` 1, `adapters` 2 (elsewhere in `adapters/`,
  none in `persistence/profile/`, `S31`'s own scope, confirmed zero
  there).
- Recorded three named blockers, not merely "it's big":
  1. **Wire-shape risk.** 55 of 81 sit in the CLI/MCP wire-facing layer.
     A retype there changes JSON schema shapes — the schema-conformance
     and MCP `output_schema` surface `W08.P13` already has standing
     concern over — a materially different risk class than an
     application-layer field, where a shape narrowing is invisible to any
     external consumer.
  2. **Undrawn boundary.** `bucket_id` is the family carrying 630
     annotated parameters behind the unmade parameters-versus-fields
     scope ruling (per the reference document's own measured figures). A
     fields-only retype today would execute against a boundary nobody has
     drawn yet, and a later ruling that folds parameters in would then
     need to reconcile against work already landed under a narrower read.
  3. **Tree state.** The tree is 567-red under triage with 432 dirty
     paths right now. An 81-site wire-facing change is the wrong thing to
     land into that state regardless of the other two blockers.

## Outcome

COMPLETE against this row's own gate (report, not retype). No code
changed. Disposition: the population is named, measured, and blocked for
three independent, named reasons — not silently dropped and not
autonomously opened. A future row may open it once the schema-conformance
risk is assessed, the params-versus-fields ruling lands, and the tree
stabilizes; none of those three preconditions is this row's to resolve.

## Notes

No incidents. This row exists so the 81-site population has a place in
the plan rather than living only in a chat report — a future reader of
the plan document sees the population, its blockers, and its disposition
without needing this session's conversation history.
