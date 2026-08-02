---
tags:
  - '#exec'
  - '#release-pipeline-full-automation'
date: '2026-08-02'
modified: '2026-08-02'
body_schema: 'body-v1'
body_hash: 'sha256:81d3999993bb6acdb089a3ff2b3651606ab3a8db351d2c0b033542ed9ba15739'
step_id: 'S13'
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
     The S13 and 2026-08-02-release-pipeline-full-automation-plan placeholders are machine-filled by
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
     The Add the OP-11 toolchain precondition refusing the bump stage instructively when node is absent from the runner, because release-please shells out through npx and whether the self-hosted Linux fleet carries node is unverified and named by the ADR as a plan precondition, gate: uv run --no-sync pytest dev/release/tests/test_version_bump.py -q passes with a case asserting the refusal names the provisioning action when the probe reports node missing and ## Scope

- `dev/release/version_bump.py`
- `dev/release/tests/test_version_bump.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Add the OP-11 toolchain precondition refusing the bump stage instructively when node is absent from the runner, because release-please shells out through npx and whether the self-hosted Linux fleet carries node is unverified and named by the ADR as a plan precondition, gate: uv run --no-sync pytest dev/release/tests/test_version_bump.py -q passes with a case asserting the refusal names the provisioning action when the probe reports node missing

## Scope

- `dev/release/version_bump.py`
- `dev/release/tests/test_version_bump.py`

## Description

- Add `run_release_please_dry_run(repo_root, *, token, repository,
  npx_executable=None, target_branch="main", config_file=None,
  manifest_file=None, timeout=...)`, shelling out to the exact
  `release-please@16 release-pr --dry-run --debug` invocation `just release`
  already runs. Checks `shutil.which("node")` FIRST, before ever attempting
  `npx`, and refuses naming OP-11 and the provisioning action when node is
  absent -- release-please shells out through `npx`.
- Add `parse_computed_version(log)`, a pure function trying a small,
  deliberately conservative set of known release-please output shapes (a
  `"version": "X.Y.Z"` JSON field, a `chore(main): release X.Y.Z` line) and
  refusing outright when neither matches, so an unrecognised log shape fails
  loudly rather than silently returning a wrong version.
- This closes the `See Also` cross-references the S09 module docstring
  already named but had not yet implemented.
- Extend `dev/release/tests/test_version_bump.py`: a real environment with
  `PATH` blanked (mirroring `test_readiness.py`'s `gh`-unresolvable pattern,
  not a mocked resolver) proves the node refusal fires and names both OP-11
  and "provision"; two `parse_computed_version` cases exercise each
  recognised shape against a synthetic fixture log; one exercises the
  refusal on an unrecognised shape.

## Outcome

Gate green: `uv run --no-sync pytest dev/release/tests/test_version_bump.py -q`
passes 23/23 (19 from S09-S11 plus 4 new), including the node-absent case
asserting the refusal names the provisioning action.

## Notes

**Honesty note, carried from S09's grounding and now load-bearing here:**
`parse_computed_version`'s two recognised shapes are UNVERIFIED against a
real successful release-please run. Grounding this Phase live-tested the
real `npx release-please@16 release-pr --dry-run --debug` invocation three
times (reported to the coordinator as a standalone finding before S09
landed): this repository carries no `v*` git tag and no matching GitHub
Release, so release-please cannot anchor its commit walk, falls back to
walking the entire history commit-by-commit, and every live attempt either
timed out or died on a genuine GitHub API 504/503 before reaching a success
path. No real "computed version" log text was ever observed. The two
patterns in `_VERSION_ANNOUNCEMENT_PATTERNS` are the best-grounded guess
available (a JSON `version` field is how release-please's manifest-mode
internals represent a `ReleasePullRequest`, and `chore(<component>): release
X.Y.Z` is release-please's own well-documented commit-message convention,
visible in this repository's own `.release-please-manifest.json`-adjacent
history) but are NOT proven against this tool's actual dry-run debug output.
The design is fail-closed specifically because of this: an unrecognised log
shape refuses rather than silently returning a wrong version, so a wrong
guess here cannot corrupt a release, only block one with a named refusal.
This should be re-verified against a real successful dry-run once the
missing release-anchor gap is resolved (a candidate operator item, not
performed here -- creating a `v0.1.0` tag/release retroactively is a
forge-mutating action outside this Step's authority).

**Addendum (same day, post-landing):** the coordinator took the tag/release
question to the operator directly rather than deciding it. Operator's
answer: manual tag/release pre-creation is exactly the "not automated"
category being rejected; the executor must handle a repo's genuine first
release on its own. Researched release-please's own documentation
(`docs/manifest-releaser.md`) for a genuine bootstrap path and found one:
the top-level `bootstrap-sha` key in `release-please-config.json`, purpose-
built for "the first time running... on a repo" -- it bounds the commit
walk without needing any prior tag or GitHub Release to exist, and
release-please ignores it once a release PR it generated has merged (self-
retiring, never legacy configuration to maintain). Added `bootstrap-sha:
70ca8b18940db8e4a9d465d631df52c02973b011` (the commit that recorded the
current `0.1.0` manifest floor) to `release-please-config.json`, added the
matching `Optional[str]` field to the strict `ReleasePleaseConfig` pydantic
model in `src/cadrumo/tests/test_release_config.py` (which has
`extra="forbid"`, so the key would otherwise fail that gate), and a
regression asserting it is present and a full 40-char SHA. This is an
ordinary committed config change, not a tag/release/forge-mutating action.
Live verification that it actually avoids the full-history walk needs the
change reachable via the GitHub API at the queried branch (release-please
fetches config remotely, not from local disk) -- this worktree is 30+
commits ahead of `origin/main` from concurrent campaigns, so pushing to
verify is a bigger, shared-worktree-wide decision outside this Step's
authority to make unilaterally; deferred back to the coordinator.

**Second addendum (same day): live verification landed.** The coordinator
pushed local `main` to `origin` (a decision made explicitly by them, not by
this Step). Re-ran the real `npx release-please@16 release-pr --dry-run
--debug` against `nevenincs/cadrumo` @ `ac6305809d`: it completed cleanly,
`rc=0`, in under five minutes, computing `0.2.0` from `v0.1.0`. Honest
reading of the log: the walk was bounded at exactly 500 commits --
release-please's own `commit-search-depth` DEFAULT, confirmed by the debug
line `√ Considering: 500 commits` -- and never reached the `bootstrap-sha`
target commit at all. So on the run that actually succeeded,
`commit-search-depth`'s default is what bounded the walk, not
`bootstrap-sha`; whether the earlier 504/503 failures were caused by the
absence of a bound (which `bootstrap-sha` targets) or were ordinary
transient GitHub API instability under sustained sequential-call load
remains genuinely unresolved with one data point. `bootstrap-sha` stays
configured regardless -- it is release-please's own documented answer to
this exact scenario, is self-retiring, and can only help.

`parse_computed_version`'s patterns were WRONG for the real output shape and
have been corrected using the real captured log: release-please renders the
version inside a `<details><summary>0.2.0</summary>` tag and a `##
[0.2.0](.../compare/v0.1.0...v0.2.0) (DATE)` changelog heading, NOT in the
PR title (a `pullRequestTitlePattern miss the part of '${version}'` warning
in this repo's config means the title carries no version at all -- a minor,
separately-fixable config gap, not blocking). The two original guessed
patterns (a bare JSON `"version"` field, a `chore: release X.Y.Z` title)
never matched real output and are retained only as a defensive fallback for
a differently-configured release-please invocation. Added
`test_parse_computed_version_extracts_from_a_real_captured_dry_run_log`
using a trimmed excerpt of the actual captured log (not a synthetic guess)
asserting `0.2.0` is extracted correctly. Docstrings updated from
"UNVERIFIED" to citing the specific verified run. 24/24
`test_version_bump.py` cases pass; ruff clean.
