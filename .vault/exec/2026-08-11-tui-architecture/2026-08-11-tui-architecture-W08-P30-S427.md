---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:4c45a3de51b04acf2e4d357a662304f4bb3aaceec978219dc8e8de987c56e45b'
step_id: 'S427'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Pin a render run to one source revision, because a long run silently mixes two. MEASURED 2026-09-04: the full matrix takes about twenty-five minutes and captures each surface in its own subprocess, so code landing mid-run splits the output. Frames captured before the table-width work show clipped headers and severed cells; frames captured after show the fix. The manifest claims all 174 equally, the stale-frame purge only removes EARLIER runs, and nothing marks which half is which -- strictly worse than the stale frames it replaced, because those at least came from another run while these are all reported as current. Record the source revision a run captured against, and either refuse to write a manifest when the tree changed during it or mark the affected frames, so a reviewer is never handed an internally inconsistent set that looks coherent.

## Scope

- `dev/tui/_artifacts.py and dev/tui/cli.py`

## Changes

- `M` `dev/tui/_artifacts.py`
- `M` `dev/tui/cli.py`
- `M` `dev/tui/tests/test_tui_visual_inventory.py`
- `verify:` `pytest -n0 -m '' dev/tui/tests` -> `pass` (51)

## Notes

A manifest now records the fingerprint of the rendered source at BOTH ends of a
run, and the writer refuses when they differ: nothing is written, and the
operator is told the tree moved. A full matrix runs about twenty-five minutes
and renders each surface in its own subprocess, so an edit landing inside that
window splits the output -- and a manifest carrying only `generated_at` claims
every frame equally. That is worse than serving stale frames from an earlier
run, because those announce themselves as another run while these are all
reported as current. It happened during this campaign: a matrix spanned the
table-width work and produced 174 frames in which some tables were clipped and
some were not.

The fingerprint is CONTENT-based, not a git revision. A render is normally
started from a dirty worktree, where `git rev-parse HEAD` is identical before
and after an edit and therefore blind to exactly the change this guards
against. Hashing the files the renderer walks answers the real question: is the
code that rendered frame 1 the code that rendered frame 174.

The fields are required rather than defaulted. A default would let a manifest
that never measured its source read as one that measured it and found no
change, which is the same collapse of "unknown" into "fine" this campaign has
been removing everywhere else.

Teeth proven by making `spans_a_source_change` return False: the gate fails
with `a run whose source changed between its first and last frame reports as
coherent`. Restored by copy and verified.

One correction made mid-step. The fingerprint test first edited the real
`home.py` and restored it in a `finally`. That works until the worktree -- which
is shared, and which a concurrent writer sweeps with broad commits -- is
committed during the second the file is modified, a hazard that has already
captured a transient synthetic defect twice in this campaign. `source_fingerprint`
now takes an injectable root and the test fingerprints a temporary tree, which
also let it assert two things the original could not: that a NESTED module
moves the fingerprint, and that a non-source file does not.
