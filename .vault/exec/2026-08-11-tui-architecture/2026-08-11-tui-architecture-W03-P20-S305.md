---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-28'
modified: '2026-08-28'
body_schema: 'body-v2'
body_hash: 'sha256:e16601f092a91abe9b39a905a2e447912ca9df4388595aa345a22046537b1321'
step_id: 'S305'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Give the Workspace projection a registry-closure facet to be parity-proven against, or record that it has none: neither admission populates registry_closure_limbs, which stays at its empty default on every assembled result, and no closure-resolving function exists, so the closure parity the proof Step names has nothing to compare and cannot be written; either implement the closure facet and prove it matches the canonical closure authority the way the work review is proven against its sole public producer, or rule that the projection carries no closure and remove the expectation from the proof surface rather than leaving a property named but unprovable

## Scope

- `src/cadrumo/application/modelo/workspace.py closure facet resolution`
- `workspace_models.py registry_closure_limbs`
- `and a closure parity proof or its documented absence`

## Changes

- `M` `src/cadrumo/application/modelo/workspace.py`
- `M` `src/cadrumo/application/modelo/tests/test_workspace_projection.py`
- `M` `src/cadrumo/application/modelo/tests/test_workspace.py`
- `verify:` `uv run --no-sync pytest src/cadrumo/application/modelo/tests/test_workspace_projection.py -m integration -n0` -> `pass`
- `verify:` `uv run --no-sync pytest src/cadrumo/application/modelo/tests/test_workspace.py src/cadrumo/application/modelo/tests/test_workspace_models.py src/cadrumo/application/modelo/tests/test_workspace_dependency_receipt.py -m integration -n0` -> `fail`
- `verify:` `uv run --no-sync pytest src/cadrumo/application/modelo --collect-only -q` -> `pass`
- `verify:` `uv run --no-sync ruff check` / `ruff format` / `ty check` on the three paths -> `pass`

## Notes

**The defect was a denominator that misstated itself, not a missing field.**
`ModeloWorkspaceReadinessPortV1` and `ModeloWorkspaceClosurePortV1` were
already complete, both with zero callers, while `graded_snapshot_contributors`
returned six and its own docstring asserted six was the complete graded set.
That tuple is not descriptive: every bounded facet revalidates against it and
both `contributor_stamp_digest` and `contributor_epoch_digest` are derived from
it, so a contributor absent from it produces a baseline token that under-reports
the assembly it claims to pin. Downstream reads that set as authoritative,
which makes an understated denominator worse than an unpopulated field. The
reasoning now lives in that function's docstring.

**The Step row's alternative branch was overturned by the governing record.**
The row offered "or record that it has none" as a real outcome. The accepted
registry API gate ADR states that graded snapshot captures all eight registered
contributors, lists `closure` among them, and says registry completeness is
selected from the cross-authority closure report. Recording "it has none" would
therefore have narrowed an accepted decision rather than reported a finding.
The row also stated that no closure-resolving function exists; two do, and one
of them is a purpose-built workspace port.

**Scope widening, recorded deliberately.** The row named the closure facet
only. Closure and readiness were built together on an explicit ruling, because
the contributor tuple, the baseline signature and both docstrings change once
either way, and shipping seven of eight against an ADR that says eight would
have relocated the "named but unprovable" property from closure to readiness
rather than ended it. The ADR governs over the row.

**A hollow proof was written and then corrected.** The first closure parity
test computed its expected value by calling the same selector the assembler
uses. A runtime mutation making that selector return an empty tuple PASSED,
because both sides collapsed together. Both proofs were rewritten to derive
their expectations independently: the closure test narrows the canonical
capture with its own comprehension and asserts the narrowed set is non-empty;
the readiness test compares axis by axis against the canonical readiness
report rather than against the projector the assembler used.

**Mutation results after that correction.** An unnarrowed selector fails; a
selector returning an empty tuple fails, and it is coordinate-valid so only the
new assertion can catch it; a readiness projector returning `None` fails, and
the field is optional so no model validator catches it either. The unmutated
run passes. All mutations were runtime monkeypatches loaded from outside the
repository; no tracked file was edited and the plugins were deleted.

**One failure in the wider run is not attributable to this work.** The
public-module fixed-point gate refuses any tracked file containing a retired
private-module string, and the two remnants are prose in files this change did
not author those lines in; one of them was never opened here. No added line
from this change contains that string.

**Provenance.** This work was committed by another agent's broad commit
`ccfddea81a` before its author reached the commit step. Content was verified
intact at HEAD across all three paths. History was not rewritten. No commit
subject names this Step.

**Production reachability, stated without inflation.** The Workspace V1 surface
is pre-consumer. `resolve_graded_snapshot_result` has no CLI or TUI caller
anywhere in the shipped package; only tests reach it. What this Step built is
reached by the sole public producer of the projection and by nothing beyond it.
The captures do run against real bundled artefacts -- the real source
connectivity census, the real registry authority, a real seeded work unit and
calculation -- so the wiring is genuinely exercised, but no operator can yet
observe a closure limb. A green Step here must not be read as operator reach.

**Discovery provenance.** Codebase discovery for this Step ran against the
local fallback index; the semantic search service was unavailable and no repair
to the shared tool environment was attempted.
