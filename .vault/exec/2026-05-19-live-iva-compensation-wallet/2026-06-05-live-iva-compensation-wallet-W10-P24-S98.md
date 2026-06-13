---
tags: ['#exec', '#live-iva-compensation-wallet']
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S98'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
---


# W10.P24.S98 vaultspec-rag service diagnostics

Scope: Wave W10, Phase P24, Step S98.

## Description

- Verify resident `vaultspec-rag` service routing for live IVA semantic discovery.
- Confirm service-unavailable and timeout states fail with typed diagnostics instead of silent in-process fallback or local Qdrant lock contention.
- Record residual service stability limitations separately from the successful typed-diagnostic behavior.

## Outcome

The current `vaultspec-rag` CLI enforces the resident-service contract when `--port 8766` is supplied. With the service stopped, `vaultspec-rag search ... --port 8766 --json` returned a typed `port_unreachable` envelope with remediation and explicitly refused silent fallback.

Starting the service with `vaultspec-rag server service start` succeeded and `vaultspec-rag server service status` reported `running`, `ready`, CUDA enabled, models loaded, same-project local backend access serialized, and an exclusive local Qdrant process model.

A service-routed code search with the default 10 second budget returned a typed `mcp_search_timeout`. Re-running the same live IVA query with `--timeout 120 --json` succeeded via MCP and returned the live IVA CLI/backend surfaces, including `src/aeat/entrypoints/cli/_app_live.py` and `src/aeat/application/live/__init__.py`.

Residual risk: after the successful code search, a subsequent vault search saw `port_unreachable`, and service status reported `crashed (port silent)`. Service logs show port-binding collisions during overlapping service starts. This is no longer a silent discovery failure or qdrant-lock ambiguity, but the upstream service stability issue remains for the RAG team/tooling backlog.

No AEAT filing, payment, confirmation, represented-taxpayer selection, or write path was executed.

## Notes

No application code was changed for this step. The closure is based on typed tooling behavior now visible to AEAT plan execution: stopped service, unreachable port, search timeout, and crashed service states are reported explicitly and can be recorded in audits instead of being mistaken for completed semantic discovery.
