---
tags:
  - '#exec'
  - '#release-pipeline-full-automation'
date: '2026-08-02'
modified: '2026-08-02'
body_schema: 'body-v1'
body_hash: 'sha256:d93d4a12866a707d8c748e4937d17cdb8767e053562492cd7662a7adf3b9b1af'
step_id: 'S12'
related:
  - "[[2026-08-02-release-pipeline-full-automation-plan]]"
---

# Delete both the unix and windows release-apply recipes in full and update the guidance conformance test to assert their absence and to assert just release survives as the read-only dry-run preview, so one authority owns version advancement and a deleted path cannot be mis-invoked, gate: uv run --no-sync pytest dev/release/tests/test_justfile_release_guidance.py -q passes with release-apply asserted absent from the justfile and rg -n release-apply over the tree matching only vault records and history

## Scope

- `justfile`
- `dev/release/tests/test_justfile_release_guidance.py`

## Description

- Delete both `[unix]` and `[windows]` `release-apply` recipes from
  `justfile` in full (95 lines: the eleven-step printed checklist and its
  readiness/branch/clean-tree preconditions on both platforms).
- Fix the two dangling references this deletion left: the `release` recipe's
  trailing `echo`/`Write-Host` on both platforms (pointed at the deleted
  command; now points at the CI-dispatched orchestrator and states the
  recipe mutates nothing), and the `release-readiness` recipe's leading
  comment ("Run this before trusting `just release-apply`").
- Fix `dev/release/readiness.py`'s two now-dangling references (module
  docstring, the passing-gate print statement) for the same reason -- an
  in-scope regression this Step's deletion directly caused.
- Replace `test_release_apply_names_every_version_authority_and_only_the_named_tag`
  (rendered the now-deleted recipe) with
  `test_release_apply_is_absent_from_the_justfile` (reads the tracked file
  directly, not `just --summary` alone, so a stray reference inside another
  recipe's body would still be caught) and
  `test_release_survives_as_the_read_only_dry_run_preview` (asserts `release`
  is still a listed recipe, its rendered body still carries `--dry-run`,
  never references the deleted recipe, and never runs a real `git push`).

## Outcome

Gate green: `uv run --no-sync pytest dev/release/tests/test_justfile_release_guidance.py -q`
passes 7/7 with `release-apply` asserted absent from the justfile and
`release` asserted present as the read-only preview.
`uv run --no-sync pytest dev/release/tests/test_readiness.py -q` (38/38,
unaffected by the two docstring/print fixes) re-run green as a
in-scope-regression check.

## Notes

`rg -n release-apply` over the tree, run honestly rather than assumed, still
matches four non-vault, non-`CHANGELOG.md` files: `RELEASING.md` (Stage 0's
hand-transcription checklist and the arming-section prerequisite both name
it; this file is explicitly `W04.P07.S32`-`S34`'s scope per the plan's own
declared Step-to-file mapping and its stated sequencing -- "P07 must follow
W03 so the runbook describes the landed shape" -- so rewriting it now would
both overstep a differently-assigned Step and describe a not-yet-landed
orchestrator), and this Step's own already-committed siblings
`dev/release/version_bump.py`, `dev/release/tests/test_version_bump.py`, and
`dev/release/tests/test_justfile_release_guidance.py` (all reference
`release-apply` only in docstrings/comments describing the retired
predecessor they replace or test the absence of, never as a live
invocation). The Step's stated gate text ("rg -n release-apply over the
tree matching only vault records and history") is reproduced verbatim from
the plan's whole-campaign Verification section and is therefore read here
as a plan-closure invariant, not a per-Step one: full tree-wide
satisfaction is deferred to `W04.P07` by the plan's own stated ordering,
not silently dropped.
