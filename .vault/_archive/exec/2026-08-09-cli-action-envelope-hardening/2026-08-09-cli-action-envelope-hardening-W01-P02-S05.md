---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:35a95dd416869a809162f53a544a77da50de6f3996b3712257193102923a4168'
step_id: 'S05'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---
# Expose live Click leaf identity and complete required-input metadata for action binding validation

## Scope

- `src/cadrumo/entrypoints/mcp/_input_schema.py`

## Description

- Derive immutable resolved Click-leaf descriptors from the registered schema key, canonical Click path, symbolic path aliases, and callback inventory.
- Derive complete required-input metadata from the live projected Click parameters, retaining argument and option shape, flags, multiplicity, type, choices, and requiredness.
- Preserve typed unresolved-leaf evidence through `VerbLeafResolutionFailure` and fail schema construction closed.
- Represent the bare root, `app`, and `config` callbacks with their real canonical paths, including the legitimate empty root path.
- Replace untyped coverage-failure input with typed records and prove the contract through direct live-tree MCP tests.

## Outcome

The input-schema projection now supplies the identity and required-input evidence consumed by later action-binding validation without introducing the Wave 02 action model early. The descriptor keeps registered subject identity distinct from executable canonical Click paths and from symbolic aliases.

## Verification

`uv run --no-sync pytest -n 0 -m integration src/cadrumo/entrypoints/mcp/tests/test_input_schema.py -k "root_status or root_app" -q`

`2 passed, 14 deselected in 2.60s`

`uv run --no-sync basedpyright src/cadrumo/entrypoints/mcp/_input_schema.py src/cadrumo/entrypoints/mcp/tests/test_input_schema.py src/cadrumo/entrypoints/mcp/tests/test_tools_and_dispatch.py`

`0 errors, 0 warnings, 0 notes`

`uv run --no-sync ruff check src/cadrumo/entrypoints/mcp/_input_schema.py src/cadrumo/entrypoints/mcp/tests/test_input_schema.py src/cadrumo/entrypoints/mcp/tests/test_tools_and_dispatch.py`

`All checks passed!`

A direct runtime projection returned `root.status` as callback identity `root.status` with `()`, and `root.app` as callback identity `root.app` with `("app",)`.

## Notes

The real `root.config` callback probe remains blocked outside this Step: lazy materialisation raises because `ModeloPriorDomiciliationElectionRefusedError` has no declared ErrorCode registry entry. The combined focused integration invocation reports 99 resolutions with that same external signature. The unresolved schema surface therefore fails closed with typed subject key, attempted path, resolved prefix, and reason; no foreign registry or Modelo code was modified.
