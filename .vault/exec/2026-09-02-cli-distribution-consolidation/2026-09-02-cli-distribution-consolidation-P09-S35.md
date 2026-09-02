---
tags:
  - '#exec'
  - '#cli-distribution-consolidation'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:60b0e4724ae13806ba4f07b21d29051f5969e712832840981a68854538304c46'
step_id: 'S35'
related:
  - "[[2026-09-02-cli-distribution-consolidation-plan]]"
---

# Prove both console scripts from the built wheel in an isolated interpreter

## Scope

- `dev/smoke/smoke_check.py`

## Changes

- `M` `dev/smoke/smoke_check.py`
- `verify:` `uv run --isolated --no-project --find-links var/distributions --with cadrumo==0.2.2 dev/smoke/smoke_check.py` -> `pass`

## Notes

The check covered one console script and asserted nothing about the second, so an
artifact that shipped without a working `cadrumo-mcp` would have passed. It now proves
the script resolves, offers its real option, and that the server runtime the entry point
defers importing is actually present in the artifact. The server is not started: it is a
stdio transport and would block until its peer closed the stream.

Teeth demonstrated by running an altered copy naming a console script that does not
exist; the run failed at the new check with a non-zero exit while every earlier check
still passed. The altered copy was kept outside the tree.

Measured against the locally built wheel on Windows rather than on the three hosted
runners the publish workflow uses.
