---
tags:
  - '#exec'
  - '#canonical-identifiers'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:5345eb53da7a8b12c19cd5d4f6655496eada8b58d392f1d47eca6df30e4242dc'
step_id: 'S56'
related:
  - "[[2026-08-07-canonical-identifiers-plan]]"
---

# add a golden-schema pinning test capturing each enumerated class's `model_json_schema()` output (the CLI envelope shape) and, for classes backing an MCP tool, the MCP `output_schema` from `_output_schema_for`, asserting the pinned constraints match the enrolled type

## Scope

- `src/cadrumo/entrypoints/mcp/tests/`

## Description

- Add one golden-schema pinning module covering both operator surfaces: the CLI envelope shape from each registered payload's own schema, and the model-facing output schema assembled from the same registry.
- State every expected constraint object as a literal transcribed from the alias declarations, never computed from the alias, so a loosened alias cannot loosen its own expectation in lock-step.
- Classify fields against the live alias objects by carried metadata rather than whole-annotation equality, so an overlay that relaxes a bound on an alias-typed field cannot escape the sweep.
- Guard the discovered sweep with a floor of named sites, so a field regressed to a plain string fails rather than quietly leaving coverage.
- Assert cross-surface parity of published string bounds, scoping the one sanctioned asymmetry to result thinning.

## Outcome

The pin lives on the model-facing side, not beside the existing single-payload pin. The deciding constraint is import ownership: the function that assembles the model-facing output schema is private to its own package, so a test on the CLI side could only reach it through a cross-package private import, which the architecture boundary forbids. The reverse direction costs nothing, because the CLI's payload classes arrive through the public schema-registry facade, so one module covers both surfaces instead of splitting one contract across two homes.

Nine assertions, all green over the live surfaces. The sweep covers all 214 alias-typed sites; five parametrised cases assert the literal pinned constraint object is present in the model-facing schema for a representative command per family; parity compares the two independently generated schemas against each other rather than against the pinned table, so it also catches divergence in shapes the table does not enumerate.

No CLI-versus-model-facing disagreement exists at HEAD once result thinning is accounted for. The one difference found is legitimate and by design: a thinned verb's schema drops its bulk array's item shapes and adds a length-bounded resource-marker string the CLI envelope never carries. Both directions are scoped to the declared thinned-verb set, so an unthinned verb must publish identical bounds on both surfaces.

The unadvertised CSV pattern is pinned as an absence, paired with a real-behaviour assertion that the pattern is still enforced: a lowercase value normalises and a separator-bearing value refuses. Pinning the absence alone would read as unconstrained beyond length, which is false.

## Notes

The first draft of the model-facing assertion was tautological and was rewritten. It classified schema leaves into families by matching them against the pinned table, then asserted that no unpinned family appeared, a condition that cannot fail because the classifier only ever emits families the table defines. It now asserts that a specific literal constraint object is present in a specific command's advertised schema, which fails when that surface loosens or drops it.

The bite proof found a real hole in the first classifier and drove a fix. Overlaying a looser bound on an alias-typed field flattens the annotation, so the alias object no longer appears in it and an equality-only classifier dropped the field out of the sweep entirely, letting precisely the cheapest loosening vector pass unnoticed. Classification now also matches on the alias's carried metadata, which survives the flattening.

Bite proof, run from a throwaway script outside the repository with no tracked file edited; each probe mutates only in-process state and restores it:

- Overlaying a relaxed lower bound on a hex-64 identity field reds the sweep, reporting the advertised object against the pinned one.
- De-typing a named CSV site back to a plain optional string reds the named-site floor, reporting the expected family against none.
- Loosening one command's registered payload reds the model-facing literal assertion, reporting that the pinned CSV shape is no longer advertised.

All three restored to green immediately afterwards, and the module passes nine of nine.

The existing single-payload pin for the expediente declaration identifier still stands on the CLI side. This module's sweep subsumes it, because that field is one of the 214 sites and one of the named floor entries, but the two are different assertion shapes rather than a duplicated idiom, and retiring the narrower one would orphan the execution record that cites it. Consolidation is flagged to the plan owner rather than taken unilaterally.
