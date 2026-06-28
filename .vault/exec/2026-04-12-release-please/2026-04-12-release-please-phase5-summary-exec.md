---
tags:
  - "#exec"
  - "#release-please"
date: 2026-04-12
modified: '2026-04-12'
title: release-please phase-5 summary — gates, review, commit
related:
  - "[[2026-04-12-release-please-plan]]"
  - "[[2026-04-12-release-please-adr]]"
  - "[[2026-04-12-release-please-research]]"
  - "[[2026-04-12-release-please-phase1-task1-exec]]"
  - "[[2026-04-12-release-please-phase2-task1-exec]]"
  - "[[2026-04-12-release-please-phase3-task1-exec]]"
  - "[[2026-04-12-release-please-phase4-task1-exec]]"
issue: wgergely/aeat#60
---

# exec summary: release-please local-only autorelease

## deliverables

- `release-please-config.json` (pinned, `release-type: python`,
  full changelog-sections, `extra-files` → `__init__.py`).
- `.release-please-manifest.json` (`{".": "0.1.0"}`).
- `CHANGELOG.md` (Keep-a-Changelog header, `[Unreleased]`,
  hand-seeded `[0.1.0] - 2026-04-12` backfilled from `git log main`).
- `RELEASING.md` (prereqs, two-step workflow, conventional commits,
  version source of truth, non-goals).
- `justfile` — new `release` + `release-apply` recipes, both with
  `[unix]` + `[windows]` bodies.
- `CLAUDE.md` — new `## Commits & Releases` section.
- `tests/test_release_config.py` — 5 unit tripwires.
- Vault artefacts: research, ADR, plan, four phase-step records,
  this summary, and the code-review record.

## gates (all green on Windows)

- `just lint` — ruff: All checks passed.
- `just typecheck` — ty: All checks passed.
- `just test` — pytest: 516 passed, 1 skipped, 17 deselected
  (live tests skipped, which is the default).
- `just hooks` — prek: all hooks passed (trailing whitespace,
  eol, yaml, toml, large files, merge conflicts, private keys,
  ruff, ruff-format, ty).

## hard constraints verified

- `ls .github/workflows/` contains only the pre-existing
  `ci.yml`; **no** `release-please.yml` was introduced.
- `tests/test_no_release_please_github_actions_workflow` enforces
  this as a test going forward.
- No `[tool.pytest]` section of `pyproject.toml` was touched
  (sibling feature-15 branch owns that territory).
- No `src/aeat/` production code was modified.
- Version source of truth unchanged at `0.1.0` across all three
  surfaces.

## code-review outcome

See `[[2026-04-12-release-please-audit]]`. Verdict: **accept**.
No blocking findings.

## next actions (post-merge, human-gated)

- After this PR merges to `main`, run `just release` to preview
  `v0.2.0` (driven by the accumulated `feat(...)` commits).
- Hand-review the dry-run log, then `just release-apply` to land
  the bump and create the local tag.
- Push `main` + tag manually if desired.
