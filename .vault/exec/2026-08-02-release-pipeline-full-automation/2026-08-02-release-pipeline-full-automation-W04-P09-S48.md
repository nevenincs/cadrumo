---
tags:
  - '#exec'
  - '#release-pipeline-full-automation'
date: '2026-08-02'
modified: '2026-08-02'
body_schema: 'body-v1'
body_hash: 'sha256:a3c9b9d75effb3c1c6bf14421af56b537ea73cc9608e5877c774c32375cb9e42'
step_id: 'S48'
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
     The S48 and 2026-08-02-release-pipeline-full-automation-plan placeholders are machine-filled by
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
     The Make the rehearsal bump exercise the seven declaration surfaces, the lock regeneration, the parity re-check, and the all-destination identity guard against a discarded temporary tree rather than returning immediately after computing the version, so the rehearsal proves the stage its own prose and the decision record both claim it proves and can surface an owned or burned or below-floor version before a real dispatch, gate: uv run --no-sync pytest dev/release/tests/test_version_bump.py -q passes asserting a rehearsal run refuses a burned version and leaves no ref and no modified surface in the real repository root and ## Scope

- `dev/release/version_bump.py`
- `dev/release/tests/test_version_bump.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Make the rehearsal bump exercise the seven declaration surfaces, the lock regeneration, the parity re-check, and the all-destination identity guard against a discarded temporary tree rather than returning immediately after computing the version, so the rehearsal proves the stage its own prose and the decision record both claim it proves and can surface an owned or burned or below-floor version before a real dispatch, gate: uv run --no-sync pytest dev/release/tests/test_version_bump.py -q passes asserting a rehearsal run refuses a burned version and leaves no ref and no modified surface in the real repository root

## Scope

- `dev/release/version_bump.py`
- `dev/release/tests/test_version_bump.py`

## Description

- Add `rehearse_bump(repo_root, version, *, changelog_block, release_date,
  repository, uv_executable, git_executable, skip_network,
  own_source_commit)`: copies `repo_root` (excluding `.git`, `.venv`, build/
  cache dirs, `var/`) into a fresh `tempfile.TemporaryDirectory`, seeds a
  throwaway git history there (`git init` + one commit, so
  `commit_tag_and_push`'s HEAD-anchored floor lookup has something to read),
  runs the real `stage_bump` (seven surfaces, lock regen, parity re-check)
  and `commit_tag_and_push(push=False)` (all-destination identity guard,
  local commit/tag) against that copy, then discards the directory
  unconditionally on scope exit. Network identity checks still query the
  REAL `repository` remote (the destination a real dispatch would check
  against); only the git mutations land on the disposable copy.
- Wire `main()`'s `--dry-run` branch to call `rehearse_bump` instead of
  returning immediately after `parse_computed_version`; update both the
  `main` and the (pre-existing, now corrected) `--dry-run` help-text
  docstring paragraphs describing what the rehearsal proves.
- Add two tests: a burned-version case (`0.2.0`, on the real shipped
  `burned_versions.json` ledger) proving the rehearsal RAISES
  `VersionIdentityError` and leaves the real fixture root's manifest content
  and HEAD completely unchanged (no surface written, no ref created); a
  clean-version positive control proving the rehearsal completes the full
  chain WITHOUT raising and still leaves the real root untouched -- so the
  burned-version refusal is proven to come from genuinely running the guard,
  not from a no-op that would trivially "pass" any input.

## Outcome

Gate green: `uv run --no-sync pytest dev/release/tests/test_version_bump.py -q`
passes 26/26 (23 prior plus 2 new plus one already-landed real-log test),
including the burned-version rehearsal case asserting no ref and no
modified surface in the real repository root.

## Notes

Discovered mid-Step that the S10-era stub-`uv` test helper had been renamed
by a peer (`_write_stub_uv` -> `_write_probe_uv`, matching
`test_readiness.py`'s `_write_probe_gh` naming) between when this Step's
grounding read the file and when the new tests were written; fixed the two
new call sites to the current name. No functional change, caught immediately
by the first test run.
