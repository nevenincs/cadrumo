---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-06'
modified: '2026-09-06'
body_schema: 'body-v2'
body_hash: 'sha256:a822981acebfebc6e2c1025fa419e8843410872259adb495cb142d4d2b38391f'
step_id: 'S472'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Establish why the generated export tree gate is red and stop rather than regenerate: twenty-seven of twenty-nine enrolled trees drift only in their generation provenance with no record layout fragment differing, and the twenty-eighth is enrolled ahead of publication so publishing it would require authoring a filing-grade check-mode refusal reason

## Scope

- `dev/registry/tests/test_generated_export_trees.py` (read only)

## Changes

NOTHING WAS CHANGED. This step is the evidence for a stop.

`test_committed_tree_is_reproducible_and_check_mode_refuses_only_for_its_named_reason`
fails on 28 of its 29 enrolled trees. The failures split into two causes, and
neither is mine to close.

TWENTY-SEVEN ARE DRIFT, AND THE DRIFT IS PROVENANCE-ONLY. Sampled across three
different modelos -- `m151-2015-2022`, `m303-2022`, `m303-2025` -- the differing
set is the same single file every time:

    committed export fragment(s) differ from a fresh render: ['_generation.provenance.json']

No record layout fragment differs on any of them. The exported records are
byte-identical to a fresh render; only the generation provenance moved. The
gate's own docstring says what that means: it is "the drift gate: an edited map,
profile or design that is not accompanied by a regenerated tree reds here".

ONE IS ENROLLED AHEAD OF PUBLICATION. `m390-2022` is the only enrolled row with
no export directory at all -- I checked all 29 against the filesystem rather
than inferring it from the failure list, which was tail-truncated in my first
sweep and would have had me report 23 when the live number was 28.

## Notes

WHY I DID NOT REGENERATE, stated rather than left as silence.

* THE SURFACE HAS AN ACTIVE WRITER AND THE COUNT MOVED UNDER ME. The failing
  set was 23 in my sweep earlier today and 28 when I re-measured during this
  firing. Registry commits are landing continuously, including
  `62b0375ffb refactor(registry): canonicalise the closed vocabularies`, which
  is exactly the kind of change that moves generation provenance while leaving
  records alone. Regenerating 27 filing-grade trees underneath a refactor
  in flight is the collision that cost five reverts on
  `tui.ledger.reconciliation.direction`.

* PUBLISHING `m390-2022` NEEDS A FILING-GRADE DETERMINATION I CANNOT DERIVE.
  The gate pins each tree's check-mode refusal in `_CHECK_MODE_PENDING` with a
  named reason, and its docstring is explicit that no committed tree has reached
  a "filing-complete, operator-reviewed revision" yet. Publishing this one means
  authoring the stated reason WHY that AEAT revision is not yet reviewable. The
  render output cannot tell me that; it is an operator judgement about the
  revision's official standing.

WHAT WOULD CLOSE IT. Either the writer who is refactoring the registry
regenerates the trees as part of that work -- which is where the change belongs,
since the provenance moved because their source moved -- or an operator states
the `m390-2022` pending reason and authorises the regeneration sweep. The narrow
finding worth handing over is that the drift is confined to
`_generation.provenance.json`, so the regeneration is metadata-only and no
exported record changes.

I ALSO CORRECTED MY OWN MEASUREMENT TWICE HERE. I first read tracked-vs-present
state with a quoted `git ls-files` glob that matched nothing and concluded the
export trees were untracked; they are tracked and clean. Then I classified
causes from a captured failure list that `tail` had truncated to seven lines. In
both cases the live filesystem and a full collection answered where my
accounting had not.
