---
tags:
  - '#exec'
  - '#conformance-cli'
date: '2026-07-28'
modified: '2026-07-28'
step_id: 'S20'
related:
  - "[[2026-07-27-conformance-cli-plan]]"
---

# regenerate the API reference stubs for the new src modules via the apidocs scaffold CLI and land the deltas with the source change

## Scope

- `docs/api`

## Description

- Verify the stub tree against the module tree with the scaffolding CLI's drift
  check rather than regenerating, because a regeneration run is tree-wide and
  would sweep concurrent campaigns' unscaffolded modules into this campaign's
  commit.
- Confirm a stub exists for each of the six modules this campaign added.
- Confirm from the stub tree's own history that each stub landed inside its
  source commit rather than in a later sweep.

## Outcome

The Step is satisfied without a regeneration run. The drift check reports the
stub tree conformant, and each of the six modules this campaign added carries
exactly one stub: the revision review-status enum, the external-grounding fold,
the classification-coherence fold, the conformance profile composer, the
external-oracle corpus enum, and the rounding-code declaration.

The stronger evidence is where those stubs landed. The stub tree's history shows
them arriving inside the feature commits that added their modules, not in a
trailing documentation sweep. That is what the scaffolding rule actually asks
for, and it is what keeps the nitpicky documentation build from ever seeing a
module without a stub or a stub without a module. Executors did this
continuously as they worked, so the Step's deliverable was met before the Step
was reached.

Deliberately not run: a fresh scaffold pass. The verb regenerates across the
whole module tree, and several peer campaigns hold unscaffolded modules in this
shared worktree, so a run here would emit their stubs too and either sweep them
into this campaign's commit or leave them dirty for owners with no signal that a
generator touched them.

## Notes

Closed by the coordinator on verification rather than by an executor performing
work, because the work had already been done incrementally and re-doing it would
have been actively harmful in a shared tree.

The drift check is the right instrument here and the regeneration verb is the
wrong one, which is a distinction worth stating: the check is read-only and
scoped in its effect, while the generator is tree-wide and its blast radius
lands on other campaigns. Preferring the check is not a shortcut around the
generator; it is the correct tool for confirming a property that is already
true.

Peer campaigns' unscaffolded modules, if any exist, remain their owners' work.
This record makes no claim about the stub tree beyond the six modules named
above and the drift check's own verdict at the time it ran.
