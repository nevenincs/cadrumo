---
tags:
  - '#exec'
  - '#justfile-design'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:8e733f2f22993bbdf1a8f98ac816cdf9290d0482992aa5007bbf9dffcb71cd08'
step_id: 'S10'
related:
  - "[[2026-09-11-justfile-design-plan]]"
---

# Expose whole-registry validity as one fail-closed primitive

## Scope

- `dev/registry/conformance/cli.py`

## Changes

- `M` `dev/registry/conformance/cli.py`
- `A` `dev/registry/conformance/tests/test_lifecycle_cli.py`
- `verify:` `uv run --no-sync pytest -q --confcutdir=dev/registry/conformance/tests dev/registry/conformance/tests/test_lifecycle_cli.py` -> `pass`
