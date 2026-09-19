---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:8a2a07769c195d4b88c4fed435db90b7774cec8d5f3c5cbc572427d7829c9dbf'
step_id: 'S93'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---
# Remove MCP-authored executable descriptor prose and route transport refusals and degradation notices through canonical authority

## Scope

- `src/cadrumo-harness/src/cadrumo_harness/mcp/_tools.py`
- `src/cadrumo-harness/src/cadrumo_harness/mcp/_transport.py`
- `src/cadrumo-harness/src/cadrumo_harness/mcp/_action_capabilities.py`
- `src/cadrumo-harness/src/cadrumo_harness/mcp/tests`

## Description

- Remove executable CLI invocations from MCP descriptor presentation.
- Project timeout, incomplete-installation, soft-timeout, and warm-degradation facts through the canonical no-action helper and shared CLI resolver.
- Remove locally authored retry, reinstall, and direct-command recovery instructions from no-action refusals.
- Preserve native typed actions through strict envelope validation and serialize them only at the wire assertion boundary.
- Add structural and integration proofs for descriptor prose, terminal projections, and prohibited recovery phrases.

## Outcome

MCP descriptors now describe intent without duplicating executable command identity. All four owned transport outcomes delegate to canonical application and CLI resolution authority, and their human-facing text no longer contradicts a `NOT_APPLICABLE` no-action verdict.

The complete owned integration selection passes 39 tests. Scoped Ruff and diff checks pass. Independent review confirmed that MCP contains no direct `PreconditionVerdict` or `ConditionEvidence` construction and that `_action_capabilities.py` remains the sole MCP executable-action resolver authority.

## Notes

- VaultSpec RAG discovery identified the existing resolver home and exact source scanning confirmed no code redeclaration in the final scope.
