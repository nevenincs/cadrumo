---
tags:
  - '#exec'
  - '#object-name-declustering'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:bfedcb2b710f45b76ac0d9476742b6906c62b920150baf8e5b16817bfaeee694'
step_id: 'S07'
related:
  - "[[2026-09-02-object-name-declustering-plan]]"
---

# Declare LibCST as a direct development dependency for controlled syntax-preserving Python edits

## Scope

- `pyproject.toml`

## Changes

- `M` `pyproject.toml`
- `verify:` `uv run --no-sync python -c "import sys, libcst; from importlib.metadata import version; print(sys.version.split()[0]); print(version('libcst')); print(libcst.parse_module('x = 1').code, end='')"` -> `pass`
- `verify:` `uv run --no-sync python -c "import tomllib; tomllib.load(open('pyproject.toml', 'rb'))"` -> `pass`
- `verify:` `git diff --check -- pyproject.toml` -> `pass`

## Notes

The owned dependency declaration landed in `81bbd1d9f6`; that commit also contains unrelated Python-classifier and release-marker changes which are not attributed to this Step.
