---
tags:
  - '#exec'
  - '#distribution-installation-readiness'
date: '2026-07-16'
modified: '2026-07-16'
step_id: 'S01'
related:
  - "[[2026-07-15-distribution-installation-readiness-plan]]"
---

# Require exact-version manuals and official companions for every command-bearing install

## Scope

- `pyproject.toml`

## Description

- Add both exact-version corpus companion distributions to the base runtime dependency
  closure.
- Preserve the split files solely as a package-index size boundary rather than a
  user-visible incomplete installation mode.
- Clarify that optional capability extras are separate from the mandatory tax corpus.

## Outcome

The built root wheel declares both `cadrumo-data-manuals==0.2.1` and
`cadrumo-data-official==0.2.1` in its installed metadata. A default command-bearing
installation can therefore resolve the full corpus required for grounded CLI and MCP
tax work.

## Notes

`uv build --wheel` produced the real wheel and direct archive inspection verified both
`Requires-Dist` records. The existing real companion version-alignment test passed.
An attempted `uv run` could not replace a concurrently used `aeat.exe`; verification
continued through the existing environment without modifying or terminating the owning
process.
