---
tags:
  - '#exec'
  - '#object-name-declustering'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:663d523c366eb06a0b28e7782be393a173593e94cbdc7b6cfe944b1a0c8b09b1'
step_id: 'S08'
related:
  - "[[2026-09-02-object-name-declustering-plan]]"
---

# Refresh the locked dependency graph after the direct LibCST declaration

## Scope

- `uv.lock`

## Changes

- `M` `uv.lock`
- `verify:` `uv lock --check` -> `pass`
- `verify:` `uv run --no-sync python -c "import sys, libcst; from importlib.metadata import version; print(sys.version.split()[0]); print(version('libcst')); print(libcst.parse_module('x = 1').code, end='')"` -> `pass`
- `verify:` `git diff --check -- uv.lock` -> `pass`

## Notes

The owned LibCST resolution landed in `81bbd1d9f6`; that commit also contains unrelated classifier and release-marker changes which are not attributed to this Step.
