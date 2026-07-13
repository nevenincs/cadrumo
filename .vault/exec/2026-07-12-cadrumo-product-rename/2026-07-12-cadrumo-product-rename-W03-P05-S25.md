---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S25'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# Bind CLI program identity to `aeat` and its version and help product surfaces to CADRUMO

## Scope

- `src/cadrumo/entrypoints/cli and direct CLI structural tests`

## Description

- Derive the Typer root name, lazy root registration, pinned program name, and
  real-process argument recognition from `PRODUCT_IDENTITY.cli_executable`.
- Render the short version surface from `PRODUCT_IDENTITY.display_name` while
  retaining the lowercase distribution identifier in package diagnostics.
- Retarget installed-console and fast-path structural tests to the sole `aeat`
  executable and the `CADRUMO` display contract.
- Verify the focused CLI surface with Ruff, real subprocess tests, and live
  `uv run --no-sync` command probes.

## Outcome

The installed `aeat` entry point now renders `aeat` in generated usage lines,
recognises its real-process argument stream, and reports `CADRUMO 0.1.1` on the
short version surface. The runtime derives each value from the canonical
product identity rather than duplicating a command or display literal.

Twenty focused integration tests passed across state-free help and version,
cold startup, installed-console discovery, former-state refusal, and curated
help resolution. The live absence probe confirmed that `cadrumo` is not a
human executable.

## Notes

The default Spanish root-help catalogue still contains title-case `Cadrumo`
and two `cadrumo <comando>` guidance lines. Those catalogue-owned strings were
not changed in this runtime step; the reopened locale-authority Steps S62-S67
remain responsible for replacing them through the locale CLI. No compatibility
executable, Python import shim, state reader, or migration path was added.
