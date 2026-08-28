---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-28'
modified: '2026-08-28'
body_schema: 'body-v2'
body_hash: 'sha256:ad2344cd32733c4885ec80d88e50b1a69cb44b898079cb3c9105b5ce7af8c14d'
step_id: 'S326'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Scope the TUI boundary gate's denominator to tracked files, so a peer's untracked work cannot participate in a gate verdict: `_live_tui_boundary_violations` builds its file set from a filesystem rglob over the package root, and its docstring claims it scans every SHIPPED source file -- but an rglob picks up untracked and mid-relocation files, which are by definition not shipped, so the docstring is false and an uncommitted file belonging to somebody else is currently contributing to whether this gate passes. This is the fourth contaminated denominator found in this campaign and the first inside a shipped gate rather than a one-off count; the others were an evidence snapshot that ingested a gitignored mirror of the source tree, a consumer census whose paths were 44 per cent that same mirror, and a vacuity screen whose denominator was 86 per cent phantom paths. Read the file set from `git ls-files` instead, keep the docstring's claim and the implementation in agreement, and prove the fix by placing an untracked file that would violate the boundary and asserting the gate does NOT consider it, alongside a tracked one that it does

## Scope

- `the TUI boundary gate's file enumeration and a tracked-versus-untracked discrimination proof`

## Changes

- `M` `dev/tests/test_import_hygiene_gate.py`
- `verify:` `uv run --no-sync pytest dev/tests/test_import_hygiene_gate.py -k "tracked_files_and_ignores_untracked or textual_is_confined or launch_seam or reaches_the_tui"` -> `pass`

## Notes

The denominator is now read from `git ls-files` rather than a filesystem rglob, so
the docstring's claim to scan shipped source is true again.

Two hazards surfaced that the Step did not anticipate and that the proof had to
handle. A fixed probe filename collides between concurrent pytest processes, hit
twice during this work, once leaving residue a later run then refused to overwrite,
so the probe is named per process. And a probe living under the package root can be
captured by the sibling `_scanned_py_files` memo and leak into another gate in the
same worker, so that walk is warmed before the probe exists.

The proof asserts both directions rather than only the exclusion: the probe is shown
to genuinely violate the boundary when handed to the scanner directly, and the cache
is cleared before re-measuring so the exclusion is not served by a memo predating the
probe.

Gate proven by mutation: restoring the rglob denominator from outside the repository
reds the proof with the intended message, naming the untracked probe in the shipped
denominator.

Scope not covered, stated because the Step is narrower than the tree: the sibling
`_scanned_py_files` in the same module feeds seven other gates from the same
filesystem walk and carries the identical contamination. It is untouched here.
