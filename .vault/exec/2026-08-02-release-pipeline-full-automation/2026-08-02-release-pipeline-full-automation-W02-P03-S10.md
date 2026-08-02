---
tags:
  - '#exec'
  - '#release-pipeline-full-automation'
date: '2026-08-02'
modified: '2026-08-02'
body_schema: 'body-v1'
body_hash: 'sha256:ce1c1107a6d462838ff77321989628afdb009bc10c41638fe8e30a3e7abdd3ea'
step_id: 'S10'
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
     The S10 and 2026-08-02-release-pipeline-full-automation-plan placeholders are machine-filled by
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
     The Add the lock regeneration and verification leg plus the version-surfaces-agree readiness re-check to the bump executor so the transcription error class the readiness check exists to catch cannot survive an automated bump either, gate: uv run --no-sync pytest dev/release/tests/test_version_bump.py -q passes with a case that plants one stale surface and asserts the executor refuses before committing anything and ## Scope

- `dev/release/version_bump.py`
- `dev/release/tests/test_version_bump.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Add the lock regeneration and verification leg plus the version-surfaces-agree readiness re-check to the bump executor so the transcription error class the readiness check exists to catch cannot survive an automated bump either, gate: uv run --no-sync pytest dev/release/tests/test_version_bump.py -q passes with a case that plants one stale surface and asserts the executor refuses before committing anything

## Scope

- `dev/release/version_bump.py`
- `dev/release/tests/test_version_bump.py`

## Description

- Add `regenerate_and_verify_lock(repo_root, *, uv_executable=None)` shelling
  out to `uv lock` then `uv lock --check`, refusing instructively when `uv`
  is unresolvable or either leg exits non-zero, mirroring `release-apply`
  checklist step 8.
- Add `verify_bump(repo_root)` re-running
  `dev.release.readiness.check_version_surfaces_agree` and raising
  `VersionBumpError` on a failed check, so the transcription-error class that
  check exists to catch cannot survive an automated bump either.
- Add `stage_bump(repo_root, version, *, changelog_block, release_date,
  uv_executable=None)` composing `apply_version` + `regenerate_and_verify_lock`
  + `verify_bump`; nothing in it touches git, so a raise anywhere in the
  chain leaves the working tree mutated but never staged or committed.
- Extend `dev/release/tests/test_version_bump.py` with a real, explicit-path
  stub `uv` executable (mirroring `test_readiness.py`'s `_write_probe_gh`
  pattern for `gh`) covering both lock legs succeeding, either leg failing,
  and `uv` being unresolvable; a `verify_bump` case plants one stale surface
  directly (not through `apply_version`) to prove the re-check catches
  staleness regardless of cause; `stage_bump` cases cover the clean compose
  and a lock-check failure refusing before any downstream stage could run.

## Outcome

Gate green: `uv run --no-sync pytest dev/release/tests/test_version_bump.py -q`
passes 15/15 (7 from S09 plus 8 new), including the planted-stale-surface
case asserting the executor refuses before anything is committed.

## Notes

None beyond the S09 record's grounding note (release-please's live
non-functional state against this repo's tag-less history), which this
Step's scope does not touch.
