---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-27'
modified: '2026-08-27'
body_schema: 'body-v2'
body_hash: 'sha256:63684783db1cf3b10b94f4438352ade00d3346b09b39fe172902df5db9aa2f78'
related: []
---

# `tui-architecture` audit: `the cadrumo-mcp server has no composition root`

## Finding

`cadrumo-mcp` is a third product entrypoint with its own console script
(`cadrumo_harness.mcp:main` -> `_server.serve`), and it composes NOTHING.
`serve()` resolves a persona, checks the SDK and runs the server loop; it never
binds the profile custody port, the login-session port, the workflow
persistence port, or any repository factory.

Every custody-touching tool therefore fails at runtime with
`RuntimeError: profile custody infrastructure has not been composed`, raised by
`profile_custody_port()` in
`src/cadrumo/application/user_profile/custody_ports.py:1278` when the
`cadrumo_profile_custody_port` ContextVar was never set.

This is a production defect, not a test artefact: the failure is in the shipped
console script, and 21 harness tests reproduce it.

## Why it was invisible

The whole harness suite failed at COLLECTION -- nine modules imported
`.session` for a module named `_session` -- so `pytest src/cadrumo-harness`
collected zero tests and reported no failures. Restoring collection
(commit `0962580257`) revealed 9 unit and 29 integration failures that had
been accumulating unseen.

The harness was rehomed out of this repository (`0a4c5377ef`) and later
restored (`415181debc`). The restore brought the client back without the
composition wiring the product's entrypoints grew in the meantime.

## The structural half

Two composition roots already exist and are near-duplicates of each other:

- `src/cadrumo/entrypoints/cli/_root_cli.py:79-115` binds ~20 ports.
- `src/cadrumo/entrypoints/tui/launcher.py:32-70` binds a similar, smaller set.

Adding a third copy inside the harness would satisfy the runtime and violate
`aeat-architecture-boundaries`, which forbids duplicated responsibilities and
requires one canonical defining module. The remediation is therefore NOT
"give the harness its own ExitStack": it is to extract the single adapter
composition both existing roots already want, and have all three entrypoints
enter it.

Fixing this in the TEST helper alone would be worse than leaving it: it would
turn a live production defect into green tests.

## Remediation

1. Extract one canonical adapter-composition context manager from the CLI root
   and the TUI launcher, in a public defining module, with the CLI/TUI
   difference (if genuine) expressed as an argument rather than two bodies.
2. Enter it from `serve()` so `cadrumo-mcp` composes what it depends on.
3. Keep the 21 connected-session tests as the proof; they fail today and must
   pass without any composition added to the test helper.

## Status

Open. Not remediated in this pass: the extraction touches two working
entrypoints, and doing it under a rapid-cadence tick risks degrading them.
The telemetry-writer half of the same suite WAS fixed (`96bbc440c8`).
