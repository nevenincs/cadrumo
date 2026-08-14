---
tags:
  - '#exec'
  - '#test-harness-sanity'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:ac7029e386617a06f6081a77d0d2f6f8bdf9762568f6212e7c299dd479452296'
step_id: 'S110'
related:
  - "[[2026-08-14-test-harness-sanity-plan]]"
---
# Sweep test helper functions assertion helpers and builders for drift the fixture census cannot see

## Scope

- `src/cadrumo`
- `dev`

## Description

- Run semantic sweeps for helper drift by BEHAVIOUR rather than identifier, across CLI invocation and envelope decoding, registry snapshot construction, profile seeding, and casilla-id coercion.
- Confirm every candidate against the real file before recording it, and apply a substitutability pre-filter before nominating any consolidation.
- Land the resulting consolidations: one manual-oracle reader, one profile registrar, one revision-id resolver, one `just` resolver, and four assertion helpers made capable of failing.

## Outcome

The census cannot see helper functions at all — it walks only decorated fixtures — so this Step covers the larger population beneath it. What the sweeps found, all verified:

- 134 private `_casilla_id` wrappers over one canonical validator, deleted outright rather than rehomed, since production and a fifth of the sites already delegated bare.
- 13 modules each reading the same bundled oracle corpus through their own private reader.
- 5 byte-identical revision-id wrappers, two of which were already dead.
- 4 subprocess CLI harnesses under 4 names with 5 bodies and no owner, and 4 raw snapshot builders reinventing a non-review-gated builder that already exists.
- 4 assertion helpers that could not fail on the thing they named — a truthiness check, a swallowed exception, an unstripped line probe, and a two-key presence test.

The method finding outlasts the individual consolidations. Describing behaviour finds a renamed twin; naming a symbol finds only that symbol. A grep for any one of these helper names returns a single site and reads as unique, which is exactly why they accumulated.

## Notes

The scoping census undercounted its own blast radius by 24%. Counting definitions answers who OWNS a symbol, never who BREAKS when it goes: five modules were shared facades, and a line-prefix search for consumers missed every multi-line import block, because the line carrying the name does not begin with the import keyword. An AST pass over import nodes surfaced 24 further files plus a second-order chain through a re-exporting `__all__`. Consumer sweeps before a deletion must be AST-based; a line-prefix grep fails at collection time, not at review time.

Two clusters were deliberately NOT consolidated, and the reasons are part of the result. Five oracle readers return an untyped mapping rather than the strict payload model — a different contract, not a lesser one, and folding them in would have made a typing decision their own suites should make. And one snapshot site hand-authors the export layout under test, which the canonical builder would unconditionally overwrite; it is constraint-shape-divergent, not duplication.

This record was authored after the row was already checked, closing an execution-record gap rather than carrying it forward.
