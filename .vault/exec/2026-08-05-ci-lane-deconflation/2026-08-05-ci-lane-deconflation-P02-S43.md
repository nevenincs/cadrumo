---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:41f8f9441a75d30cf780180058e9e3c69417195e99879f91dba0e24ac34548ca'
step_id: 'S43'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace ci-lane-deconflation with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S43 and 2026-08-05-ci-lane-deconflation-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Add the format check to the per-push blocking lane and sweep the tree that must pass it first, in that order, because ruff format --check is enforced by nothing today and the tree is far from able to satisfy it. The recipe check-format exists and is invoked by zero workflows, and the per-push Lint step runs check-style and check-relative-imports only, so the sole configured format gate is the ruff-format hook in prek.toml, which this fleet is instructed never to run because it stashes the shared tree. Two configured gates cover formatting and the intersection of what they enforce is empty, which is the same shape as a gate that exists while nothing selects it. THE ROW THIS SUPERSEDES SAID EIGHT FILES AND THAT NUMBER IS SRC-SCOPED. The recipe checks the whole repository, and measured against HEAD by excluding every file dirty in the working tree, 333 files would be reformatted, of which the eight are a subset. So the one-line workflow edit is NOT the fix on its own, because adding the step to a tree in this state reds the lane on its first run and a permanently red lane is one everyone learns to ignore, which is the failure this campaign has already documented for continue-on-error. Sequence the sweep first and the gate second, and treat the sweep as mechanical but wide, since it spans dev and src and cannot be done by pathspec while peers hold those files and ## Scope

- `.github/workflows/ci.yml`
- `justfile`
- `prek.toml` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

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
