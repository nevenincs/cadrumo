---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:5875d2c7b0e0b5529e0fd93d7831c49ceb07c129d80ab6e27eea99063eb867c4'
step_id: 'S43'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---

# Add the format check to the per-push blocking lane and sweep the tree that must pass it first, in that order, because ruff format --check is enforced by nothing today and the tree is far from able to satisfy it. The recipe check-format exists and is invoked by zero workflows, and the per-push Lint step runs check-style and check-relative-imports only, so the sole configured format gate is the ruff-format hook in prek.toml, which this fleet is instructed never to run because it stashes the shared tree. Two configured gates cover formatting and the intersection of what they enforce is empty, which is the same shape as a gate that exists while nothing selects it. THE ROW THIS SUPERSEDES SAID EIGHT FILES AND THAT NUMBER IS SRC-SCOPED. The recipe checks the whole repository, and measured against HEAD by excluding every file dirty in the working tree, 333 files would be reformatted, of which the eight are a subset. So the one-line workflow edit is NOT the fix on its own, because adding the step to a tree in this state reds the lane on its first run and a permanently red lane is one everyone learns to ignore, which is the failure this campaign has already documented for continue-on-error. Sequence the sweep first and the gate second, and treat the sweep as mechanical but wide, since it spans dev and src and cannot be done by pathspec while peers hold those files

## Scope

- `.github/workflows/ci.yml`
- `justfile`
- `prek.toml`

## Description

- Re-measure the sweep against a clean tree rather than carrying the row's
  333-file figure forward.
- Sweep the files ruff-format would change, after confirming none was held
  dirty by a peer.
- Absorb the pre-existing style red found on the way, because a format gate
  landing beside a red style gate buries it.
- Add `check-format` to the per-push Lint step, in the same commit as the
  sweep.
- Verify both gates green and the workflow conformance suites unbroken.

## Outcome

Landed as `e38c0d517f5e6def5fa017e61c41f712eaf9e387`. `just check-format` and
`just check-style` are both green at HEAD, and the per-push Lint step now runs
the format check.

THE SWEEP IS FAR SMALLER THAN THE ROW PRICED, and the row was not wrong when
it was written. It measured 333 files against a working tree it had to exclude
dirty files from. Measured against a clean tree after the merge landed, 18
files of 6314 needed reformatting. The difference is the merge, not a change of
method. All 18 were long-call-argument wraps, and none was held dirty by a
peer, so the row's warning that the sweep "cannot be done by pathspec while
peers hold those files" did not bind in the end.

Sequenced sweep-first, gate-second in ONE commit, which is the row's own
instruction and the reason it exists as a row rather than a one-line workflow
edit. Adding the step to an unswept tree reds the lane on its first run, and a
permanently red lane is one everyone learns to route around -- the decay this
campaign has already documented for `continue-on-error`.

The gate's discrimination needs no planted proof, because it was demonstrated
naturally in the course of the work: `check-format` was RED against 18 real
files before the sweep and GREEN after, on the same tree. That is a stronger
demonstration than a synthetic violation, since it fired on genuine drift
rather than on drift authored to make it fire.

ABSORBED, not deferred: `just check-style` was ALREADY failing at HEAD on a
committed unsorted import block in a registry test. The per-push Lint step was
therefore red for the whole fleet before this change, and adding a format gate
beside it would have buried a live red under a new one. The file was committed
rather than peer-held, so fixing it was safe.

## Notes

Only 9 of the 20 paths reached this commit. The other 11 formatted files were
swept into a peer's commit between the reformat and the commit, which is
ordinary in this tree and cost nothing: the content is identical either way and
the tree verifies green at HEAD. It is recorded because a reader comparing the
commit's file count against this record's 18 would otherwise suspect a partial
sweep.

The row's observation that two configured format gates existed with an empty
intersection is now half-resolved rather than resolved. `check-format` is
enforced on every push. The ruff-format hook in `prek.toml` remains configured
and remains one this fleet is instructed never to run, because it stashes the
shared tree. That is not a contradiction any more -- the push gate is now the
authority and the hook is redundant rather than load-bearing -- but a later
author removing the hook should know the push gate is what replaced it.
