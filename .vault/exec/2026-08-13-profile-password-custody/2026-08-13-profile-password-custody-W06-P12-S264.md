---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:aa912e02ff35a826ef6ba456dbdf927f51b8c5f7da7d6b7e7eb362b796652a6c'
step_id: 'S264'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---
# Restore hermetic cadrumo-mcp console-script resolution for installed-service, handshake, and watchdog subprocess proofs without weakening real executable delivery

## Scope

- `src/cadrumo-harness/src/cadrumo_harness/mcp/tests/ and src/cadrumo-harness/ packaging`

## Description

Confirm that the restored harness workspace is an editable member of the root uv environment, that its declared `cadrumo-mcp` console script resolves inside that hermetic environment, and that installed-service refusal, real-client handshakes, and the serial real-server watchdog exercise the executable rather than a module shortcut.

## Outcome

`uv run --package cadrumo-harness` resolves `cadrumo-mcp` to the root environment's `Scripts/cadrumo-mcp.EXE`. The installed-service and client-handshake modules plus the serial real-server leaked-stdin watchdog pass together with seven tests passed in 35.17 seconds under `-n0 -m integration`. The proofs launch the actual console script and require no test-only executable shim or weakened delivery assertion.

## Notes

No new packaging implementation was required at this checkpoint. Commit `9e676bff59` had already restored `src/cadrumo-harness` as a uv workspace member and root development dependency, while `415181debc` restored the distribution and its declared console entry point. S264 verifies that those canonical owners now satisfy the derived failure on the current shared head.
