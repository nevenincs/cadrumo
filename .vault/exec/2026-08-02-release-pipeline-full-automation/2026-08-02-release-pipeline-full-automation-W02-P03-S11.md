---
tags:
  - '#exec'
  - '#release-pipeline-full-automation'
date: '2026-08-02'
modified: '2026-08-02'
body_schema: 'body-v1'
body_hash: 'sha256:00ee6f92bc2d057ccc4798e9a61a2c111942f46c379f37501ce5495b85c7781a'
step_id: 'S11'
related:
  - "[[2026-08-02-release-pipeline-full-automation-plan]]"
---

# Add the commit, tag, and push leg invoking the all-destination version-identity authority BEFORE any ref leaves the runner, so a bump colliding with an owned, burned, or below-floor version refuses before a tag exists rather than after, gate: uv run --no-sync pytest dev/release/tests/test_version_bump.py -q passes against an injectable git root covering the clean bump, a burned-version refusal, and a below-floor refusal, with real push execution flagged non-local and CI-only

## Scope

- `dev/release/version_bump.py`
- `dev/release/tests/test_version_bump.py`

## Description

- Add `commit_tag_and_push(repo_root, version, *, repository, git_executable,
  push=False, skip_network=False, own_source_commit)` invoking
  `dev.release.version_identity`'s all-destination identity guard BEFORE any
  git mutation, then `git add` the staged surfaces (mirroring `release-apply`
  checklist step 9's exact file list), `git commit`, `git tag -a`, and
  (only when `push=True`) `git push` both `main` and the tag ref.
- Discover and fix a real ordering bug while building the test for this: the
  identity guard's floor check must compare the candidate against the
  manifest floor as committed at HEAD, not the working-tree file --
  `apply_version` (S09) already rewrote the working-tree manifest to the
  candidate version by the time this stage runs, so reading the floor from
  disk compared the candidate against itself and refused every bump
  unconditionally. Added `_manifest_floor_at_head` (`git show
  HEAD:.release-please-manifest.json`) and switched the guard to the pure
  `version_identity.version_conflicts` core with that floor, rather than
  `assert_version_available`'s file-path-based floor lookup.
- `push` defaults to `False`: local commit and tag only. A real `git push`
  needs a real remote and real credentials a unit test does not have, so it
  is exercised only by passing `push=True` (untested here; flagged
  non-local/CI-only per the gate).
- Extend `dev/release/tests/test_version_bump.py` with a real git-repository
  fixture (`_make_git_repo_root`, mirroring
  `dev/audit/tests/test_checkout_drift.py`'s real-git-repo pattern) covering:
  a clean above-floor non-burned bump committing and tagging locally; a
  version on the real shipped `dev/release/burned_versions.json` ledger
  (`0.2.0`) refusing with no commit or tag created; a version at or below an
  injected manifest floor refusing with no commit or tag created; and an
  unresolvable `git` binary refusing instructively.

## Outcome

Gate green: `uv run --no-sync pytest dev/release/tests/test_version_bump.py -q`
passes 19/19 (15 from S09+S10 plus 4 new), covering the clean bump, the
burned-version refusal, and the below-floor refusal against an injectable
git root, each asserted to leave HEAD and the tag namespace untouched on
refusal.

## Notes

The floor-lookup ordering bug above was caught only because the test built a
real end-to-end sequence (`apply_version` then `commit_tag_and_push` against
the same working tree) rather than testing `commit_tag_and_push` in
isolation from a hand-authored floor value -- exactly the kind of subtly-wrong
integration defect the plan's own agent-assignment note flagged this Phase
as likely to produce. Recorded here since a reviewer checking only the
individual functions' unit contracts would not see it.
