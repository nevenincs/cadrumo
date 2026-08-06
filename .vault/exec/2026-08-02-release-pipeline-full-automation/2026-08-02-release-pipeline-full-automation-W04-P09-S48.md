---
tags:
  - '#exec'
  - '#release-pipeline-full-automation'
date: '2026-08-02'
modified: '2026-08-02'
body_schema: 'body-v1'
body_hash: 'sha256:11d5e16a932c6b29f5f550b04bc2039294c80fe9e996a0efd3f84d92e9801cae'
step_id: 'S48'
related:
  - "[[2026-08-02-release-pipeline-full-automation-plan]]"
---

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
