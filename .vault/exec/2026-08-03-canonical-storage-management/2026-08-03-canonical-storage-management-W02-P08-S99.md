---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-04'
body_schema: 'body-v1'
body_hash: 'sha256:3a4ae3aebf4855bd2ea955c0c54c6c8736e679d23bdcd75c005938dbd6d91284'
step_id: 'S99'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

# Add one parameterised helper collapsing the five copy-pasted optional-root Typer resolvers, covering both the bundled-default family in registry.py and the settings-default family in registry.py and _app_live.py, so the two families stop drifting apart independently

## Scope

- `src/cadrumo/entrypoints/cli/registry.py`
- `src/cadrumo/entrypoints/cli/_app_live.py`

## Description

## Outcome

Landed in `d9145d3b83`, confirmed at HEAD. `resolve_optional_root(value: Path | None, default: Callable[[], Path]) -> Path` in `src/cadrumo/entrypoints/cli/_common.py:562` is the single parameterised helper, taking the default as a lazily-invoked callable so it computes only when the operator supplies no override (unchanged behaviour). Covers both the bundled-default family (registry/workbook/source roots) and the settings-default family (parity store root, live output roots).

## Notes
