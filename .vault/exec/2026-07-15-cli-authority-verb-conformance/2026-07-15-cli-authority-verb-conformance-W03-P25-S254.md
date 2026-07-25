---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S254'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Introduce one typed resolved registry context shared by scoped and unscoped query methods while preserving both public resolution forms

## Scope

- `src/cadrumo/domain/calculations/registry/_queries.py`

## Description

- Discover an uncommitted implementation of this step already present in the working tree and establish whether it was live peer work or stranded.
- Adopt and verify it rather than re-implement it.
- Confirm both public resolution forms survive the shared context.
- Land it with the proofs authored for S257.

## Outcome

Implemented, but the implementation was adopted rather than authored here.

The typed context existed in the working tree as uncommitted work when this step was picked up. `ResolvedRegistryQueryContext` was defined, both resolvers returned it, and every report builder had been converted to read it. The file had not been touched for roughly eight hours and the change was coherent and single-purpose, so it was stranded rather than live peer editing. It was therefore adopted and completed rather than rewritten, and no part of it was overwritten.

What the change achieves is real. `RegistryQueryService` reaches a revision by two different selection authorities: an unscoped lookup narrowing by period token alone, and a scoped lookup resolving a snapshot for an explicit filing year. Both previously returned bare tuples, and the two tuples had different arity and different element meaning, so every call site had to know which resolver it had called in order to unpack correctly. Both now return one frozen, extra-forbidding model carrying definition, revision, and the optional filing year and registry period.

Both public resolution forms are preserved, which is the constraint this step attaches. The two resolvers remain separate methods with separate selection logic; only their result shape is unified. The unscoped form leaves the filing year unset, and the model makes that optionality explicit rather than encoding it as a positional `None`. The context is also deliberately narrower than a registry snapshot, since a snapshot requires a filing year and carries legal, source and expectation authority that a read-only unscoped introspection query neither has nor needs.

Verified before adoption: the module imports, the field set is the expected four, and the pre-existing query suite passed unchanged at 21 tests. The proofs added under S257 then raised that to 25.

Committed in `003a2f987d`.

## Notes

Semantic CODE search is degraded and reports itself healthy, so the module was read directly. The stranded work would not have been found by search at all; it was found by diffing the cited file against HEAD before making any edit, which is the shared-worktree precaution that also prevented overwriting it.

This step has no counterpart in the sibling quality-backlog plan, so unlike the P24 steps its closure rests entirely on the code rather than on reconciling a sibling claim.

Worth flagging for the campaign: an implementation can be complete and still invisible, because it is uncommitted. A status read that trusts committed state alone would have reported this step as not started and invited a duplicate implementation.
