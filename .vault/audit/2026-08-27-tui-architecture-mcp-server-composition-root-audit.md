---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-27'
modified: '2026-08-27'
body_schema: 'body-v2'
body_hash: 'sha256:434e23a8cb1a8d89601be90729795cd00de836538dd5c4458a126bd3e75a90f6'
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

## Correction to this audit

The structural half above overstated the duplication. `profile_storage_scope`
in `entrypoints/tui/launcher.py` is called ONLY by `tui/devtools/fixture.py`
and binds a dev-test passphrase: it is a devtools fixture, not the installed
TUI path, and the installed TUI launches from CLI commands and inherits the CLI
root's composition. There was therefore ONE production composition root, one
devtools fixture, and one entrypoint with none -- not two near-duplicate
production roots.

The fixture's thirteen bindings were a strict subset of the CLI's twenty, so
the extracted scope needed no argument to express a CLI/TUI difference: there
was none to express.

## Resolution

`entrypoints/adapter_composition.py` now declares `profile_adapter_composition`,
and the CLI root, the TUI devtools fixture and the MCP server all enter it. The
harness integration lane went from 26 failures to 345 passing with no
composition added to the test session helper.

Where the binding is entered was decided by measurement, not preference. Two
placements looked right and fixed nothing: `serve()` (the tests reach the server
through the in-process transport and never call it) and the SDK server lifespan
(it runs inside the server task, so the request handlers spawned beside it do
not inherit its ContextVars). Binding at `build_server` construction works
because that context is an ancestor of every task the server later spawns, and
both the stdio runner and every test build the server through it.

The composition is entered once per process and deliberately never unwound: a
ContextVar token can only be reset in the context that created it, so an
exit-time unbind raises.

## Status

Closed.
