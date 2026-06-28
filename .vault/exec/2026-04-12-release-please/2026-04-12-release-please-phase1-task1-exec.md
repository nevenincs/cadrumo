---
tags:
  - "#exec"
  - "#release-please"
date: 2026-04-12
modified: '2026-04-12'
title: release-please phase-1 task-1 — config + manifest + changelog + releasing.md
related:
  - "[[2026-04-12-release-please-plan]]"
  - "[[2026-04-12-release-please-adr]]"
issue: wgergely/aeat#60
---

# exec: release-please phase-1 task-1

## intent

Land the four project-meta files the `just release` workflow depends on
(per `[[2026-04-12-release-please-plan]]` phase-1): the release-please
config, the manifest, the hand-seeded CHANGELOG, and `RELEASING.md`.

## actions

- Wrote `release-please-config.json` with `release-type: python`,
  one package at `.`, `extra-files` pointing at
  `src/aeat/__init__.py`, and every project-relevant commit type
  surfaced in `changelog-sections`. `ci` and `style` are marked
  `hidden: true` (no expected traffic — Actions is disabled; style
  commits are trivial).
- Wrote `.release-please-manifest.json` seeded at `0.1.0` to match
  the existing `pyproject.toml` / `__init__.py` versions. One key,
  one value.
- Wrote `CHANGELOG.md` with a Keep-a-Changelog-style header, an
  `## [Unreleased]` placeholder, and a hand-curated
  `## [0.1.0] - 2026-04-12` block. The block was sourced from
  `git log main --format='%s'` filtered through a
  conventional-commit regex, then grouped by type. Merge commits
  and non-conventional messages (`"push"`, `"update lock"`,
  `"merge conflict fix"`) were dropped.
- Wrote `RELEASING.md` documenting prerequisites (Node, `gh auth`),
  the two-step workflow (`just release` preview, `just release-apply`
  land), the conventional-commits mandate, the version source of
  truth, and the non-goals.

## verification

- `release-please-config.json` validates against the strict
  `ReleasePleaseConfig` pydantic model in
  `tests/test_release_config.py`.
- `.release-please-manifest.json` has exactly one key `"."` →
  `"0.1.0"`.
- `CHANGELOG.md` contains `# Changelog` and is non-empty.
- All four files are at the repo root as expected by release-please.
