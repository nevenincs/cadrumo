---
tags:
  - "#exec"
  - "#release-please"
date: 2026-04-12
modified: '2026-04-12'
title: release-please phase-3 task-1 — CLAUDE.md conventional-commits mandate
related:
  - "[[2026-04-12-release-please-plan]]"
  - "[[2026-04-12-release-please-adr]]"
issue: wgergely/aeat#60
---

# exec: release-please phase-3 task-1

## intent

Add a "Commits & Releases" section to `CLAUDE.md` documenting the
conventional-commits mandate, the LOCAL-only release workflow, and
the version source of truth. This is the project-wide agent
instruction surface, so the mandate is binding on every future
contributing agent.

## actions

- Appended the `## Commits & Releases` section to `CLAUDE.md` just
  before the `<vaultspec type="config">` block.
- Three bullets: (1) conventional-commits format + type list +
  link to `RELEASING.md` and the ADR; (2) releases run LOCALLY
  with explicit no-`release-please.yml` prohibition and the
  test tripwire reference; (3) version source of truth across
  `pyproject.toml`, `__init__.py`, and the manifest.

## verification

- `CLAUDE.md` parses cleanly (markdown-only change, no YAML).
- Cross-references resolve:
  - `RELEASING.md` exists at repo root.
  - `.vault/adr/2026-04-12-release-please-adr.md` exists.
  - `tests/test_release_config.py` exists and enforces the rules.
