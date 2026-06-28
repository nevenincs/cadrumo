---
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-31'
modified: '2026-05-31'
step_id: 'S539'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
---

# `codebase-solidification` `W08.P34.S539`

DOCUMENT: `--version` semver output deferral from `tr()` — inline comment added explaining machine-format policy. No code changes beyond the comment.

- Modified: `src/aeat/entrypoints/cli/__init__.py`

## Description

The `--version` callback emits `"{package_name} {package_version}"` via `typer.echo()` without going through `tr()`. This is intentional: version strings are consumed by scripts, package managers, and CI tooling that expect a stable machine-readable format. Wrapping through the locale resolver would make the output locale-sensitive and break tool consumers. An inline comment `# S539-DEFERRED: semver output is machine-format; tr() wrapping intentionally omitted` was added at the emit site.

## Tests

No new tests required. The `--version` output format is validated by existing CLI integration tests.
