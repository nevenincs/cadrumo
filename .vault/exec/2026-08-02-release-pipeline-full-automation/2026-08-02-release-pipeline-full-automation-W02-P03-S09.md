---
tags:
  - '#exec'
  - '#release-pipeline-full-automation'
date: '2026-08-02'
modified: '2026-08-02'
body_schema: 'body-v1'
body_hash: 'sha256:71a1aec5c06d3dd8a9875057d61289737521ece813e92a51a357014a5516c68c'
step_id: 'S09'
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
     The S09 and 2026-08-02-release-pipeline-full-automation-plan placeholders are machine-filled by
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
     The Build the bump executor that runs release-please against the manifest floor, reads the computed version rather than accepting a chosen one, and applies it to all seven declaration surfaces named by the retiring apply target, the release-please manifest, the three pyproject versions, the package dunder version, both base dependency pins, and the changelog block, gate: uv run --no-sync pytest dev/release/tests/test_version_bump.py -q passes against an injectable temporary repository root asserting each of the seven surfaces individually and asserting the build-stamped mcpb manifest sentinel is NOT touched and ## Scope

- `dev/release/version_bump.py`
- `dev/release/tests/test_version_bump.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Build the bump executor that runs release-please against the manifest floor, reads the computed version rather than accepting a chosen one, and applies it to all seven declaration surfaces named by the retiring apply target, the release-please manifest, the three pyproject versions, the package dunder version, both base dependency pins, and the changelog block, gate: uv run --no-sync pytest dev/release/tests/test_version_bump.py -q passes against an injectable temporary repository root asserting each of the seven surfaces individually and asserting the build-stamped mcpb manifest sentinel is NOT touched

## Scope

- `dev/release/version_bump.py`
- `dev/release/tests/test_version_bump.py`

## Description

- Add `dev/release/version_bump.py` declaring the seven declaration-surface
  relative paths (release-please manifest, three `pyproject.toml` versions,
  the dunder version, both companion pins as one surface, the changelog
  block) and excluding the build-stamped `.mcpb` manifest sentinel.
- Implement `apply_version(repo_root, version, *, changelog_block,
  release_date)` composing per-surface mutators, each refusing on zero or
  more than one match rather than guessing, and asserting the `.mcpb`
  manifest is byte-identical before and after the call.
- Implement `_bump_changelog` prepending a new `## [version] - date` section
  directly after the `## [Unreleased]` anchor, refusing a changelog missing
  the anchor and refusing a version the changelog already documents.
- Add `dev/release/tests/test_version_bump.py` mirroring the fixture shape
  `test_readiness.py` already established for the same surfaces, covering
  the happy path (all seven surfaces individually asserted), the
  mcpb-sentinel-untouched assertion, and four refusal cases (missing
  literal, ambiguous literal, missing manifest root entry, missing
  Unreleased anchor, duplicate changelog section).
- Ran `uv run --no-sync pytest dev/release/tests/test_version_bump.py -q`
  (7 passed) and `uv run --no-sync ruff check` on both new files (clean).

## Outcome

Gate green: `uv run --no-sync pytest dev/release/tests/test_version_bump.py -q`
passes 7/7, asserting each of the seven surfaces individually and the
`.mcpb` manifest sentinel explicitly untouched.

## Notes

Grounding this Step live-tested the real `release-please@16 release-pr
--dry-run --debug` invocation this Step's docstring describes as the future
version-computation shell. That live test surfaced an unrelated, real
blocker: the repository carries no `v*` git tag and no GitHub Release at all,
so release-please cannot anchor its commit walk and either times out or hits
a GitHub API 5xx against this repo's history (700+ commits since the last
manifest bump). This Step's own scope (`apply_version`, the seven-surface
mutation) does not depend on that shell and is fully tested here; the
version-computation shell (`run_release_please_dry_run` /
`parse_computed_version`) lands in a later Step and its exact success-path
output format is unverified pending that repo-state gap. Reported to the
coordinator as a standalone finding; not further diagnosed here.
