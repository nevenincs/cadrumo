---
tags:
  - '#exec'
  - '#object-name-declustering'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:54cf98298ff54480d812baf04df88b4ebc195d91a89af0ad1b35762da1d7dfe0'
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
