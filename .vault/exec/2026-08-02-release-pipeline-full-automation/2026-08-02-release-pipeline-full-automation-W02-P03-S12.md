---
tags:
  - '#exec'
  - '#release-pipeline-full-automation'
date: '2026-08-02'
modified: '2026-08-02'
body_schema: 'body-v1'
body_hash: 'sha256:1e6fae536c5bc692244b3be5c7bd87d962a26d2e9437520685ccb316053ea6db'
step_id: 'S12'
related:
  - "[[2026-08-02-release-pipeline-full-automation-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace release-pipeline-full-automation with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S12 and 2026-08-02-release-pipeline-full-automation-plan placeholders are machine-filled by
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
     The Delete both the unix and windows release-apply recipes in full and update the guidance conformance test to assert their absence and to assert just release survives as the read-only dry-run preview, so one authority owns version advancement and a deleted path cannot be mis-invoked, gate: uv run --no-sync pytest dev/release/tests/test_justfile_release_guidance.py -q passes with release-apply asserted absent from the justfile and rg -n release-apply over the tree matching only vault records and history and ## Scope

- `justfile`
- `dev/release/tests/test_justfile_release_guidance.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

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
