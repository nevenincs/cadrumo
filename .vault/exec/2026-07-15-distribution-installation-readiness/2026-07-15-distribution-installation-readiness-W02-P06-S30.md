---
tags:
  - '#exec'
  - '#distribution-installation-readiness'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S30'
related:
  - "[[2026-07-15-distribution-installation-readiness-plan]]"
---

# Install MCPB through each claimed client and require the real tax-work tool call

## Scope

- `packaging/mcpb/tests/test_client_install.py`

## Description

- Add a real-behavior integration test module marked `integration`, `hex_entrypoint`, and `serial` beside the existing MCPB build test.
- Resolve one canonical product cohort: reuse a cohort supplied through the `CADRUMO_MCPB_CLIENT_COHORT_DIR` environment variable or the retained `var/packaging-smoke-cohort/python` directory, otherwise build the six-file wheel-and-sdist cohort from the working tree exactly as the build test does.
- Drive the shared MCPB client-install runtime once through `run_mcpb_smoke`: build the unsigned bundle, validate the unpacked extension with the official `@anthropic-ai/mcpb` validator, provision it host-style through the manifest's `uv` launcher into the bundle-local environment, launch the server concurrently, and complete the public MCP protocol tax oracle.
- Assert the grounded Modelo 200 result `DP200014:00562 == 23000.00` under `modelo-200-cuota-integra`, non-empty legal and source references, the real work-calculate tool call, and the sole permitted `plazo_vencido_unassessed_preview` notice.
- Assert the runtime launches the manifest command adapted to the unpacked extension directory (never the source checkout), binds the exact stamped cohort digests and version, and advertises no operating-system or client support row beyond the executed Python runtime.

## Outcome

The MCPB client-install gate passes. Four tests complete in 427.94 seconds: the installed bundle provisions through the official validator plus the manifest `uv` launcher and returns the grounded oracle result from a project-independent state root, the resolved launch is the manifest command adapted to the unpacked extension, and the stamped cohort digests and version match the retained cohort. The pre-existing eight-plus-one build tests remain green (`packaging/mcpb/tests/test_build.py`, 9 passed in 272.05 seconds), so the new module introduces no regression. Focused Ruff check, Ruff format check, and ty check all pass on the new file.

## Notes

- The automated coverage proves the one MCPB install runtime that every claimed MCP-bundle client shares: the official `@anthropic-ai/mcpb` validator plus the manifest's declared `uv` launcher. It does not drive a graphical client. The per-client acceptance for Claude Desktop and the Cowork host loop remains the manual `W03.P08` rows `S39` and `S69`; the module names those clients and documents the boundary.
- The test requires `uv`, `npx`, and network access to the pinned `@anthropic-ai/mcpb@2.1.2` validator and the bundle's transitive dependency closure. A missing runtime piece fails loudly rather than skipping, per the readiness contract.
- The installed bundle is unsigned, so no publisher-signature claim is asserted; MCPB signing remains `S29`.
