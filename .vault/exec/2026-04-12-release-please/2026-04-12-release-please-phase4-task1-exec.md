---
tags:
  - "#exec"
  - "#release-please"
date: 2026-04-12
modified: '2026-04-12'
title: release-please phase-4 task-1 — tests/test_release_config.py tripwire
related:
  - "[[2026-04-12-release-please-plan]]"
  - "[[2026-04-12-release-please-adr]]"
issue: wgergely/aeat#60
---

# exec: release-please phase-4 task-1

## intent

Add a `@pytest.mark.unit` tripwire that fails fast on any drift
between the release-please config, the manifest, the CHANGELOG,
and the three version surfaces.

## actions

- Wrote `tests/test_release_config.py` with five unit tests:
  1. `test_release_please_config_is_well_formed` — parses the
     config JSON through a strict
     `ReleasePleaseConfig(extra="forbid")` pydantic v2 model and
     asserts every project-relevant commit type is present in
     `changelog-sections`.
  2. `test_release_please_manifest_is_well_formed` — parses the
     manifest JSON through `ReleasePleaseManifest(extra="forbid")`
     and asserts exactly one key (`"."`).
  3. `test_changelog_exists_and_non_empty` — asserts the file
     exists, is non-empty, and contains the `# Changelog` header.
  4. `test_version_surfaces_agree` — reads version from
     `pyproject.toml` (via `tomllib`), `src/aeat/__init__.py`
     (via regex), and the manifest JSON; asserts all three equal.
  5. `test_no_release_please_github_actions_workflow` — asserts
     `.github/workflows/release-please.yml` does NOT exist,
     encoding the ADR's hard constraint as a test.
- Location: top-level `tests/` (not colocated under `src/aeat/`).
  The ADR documents this narrow exception — the test validates
  project-meta files that belong to no `aeat.*` subpackage.

## verification

- `just test` green: all 5 new tests pass; total suite
  `516 passed, 1 skipped, 17 deselected`.
- `just typecheck` green (ty accepts the pydantic models + tomllib).
- `just lint` green (ruff passes; no rule exemptions added).
