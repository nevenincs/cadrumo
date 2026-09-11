---
tags:
  - '#exec'
  - '#justfile-design'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:eda3b05637c73bb65eae607ac1d18fc30978026f05b370d2d623a5cc29cc0c88'
step_id: 'S13'
related:
  - "[[2026-09-11-justfile-design-plan]]"
---

# Expose existing target-currentness authority-publication target-publication and digest-bound republish operations through distinct semantic entry points

## Scope

- `dev/registry/pipeline/cli.py`

## Changes

- `M` `dev/registry/pipeline/cli.py`
- `M` `dev/registry/conformance/tests/test_lifecycle_cli.py`
- `M` `justfile`
- `verify:` `uv run --no-sync python -m dev.registry.pipeline --help` -> `pass`
