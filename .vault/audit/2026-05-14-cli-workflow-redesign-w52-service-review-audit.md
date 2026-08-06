---
tags:
  - '#audit'
  - '#cli-workflow-redesign'
date: '2026-05-14'
modified: '2026-07-17'
body_hash: 'sha256:3b1d14f54ca6058a2d91356ed6ff7b09caddd6672643b1f463dadca5d03f8861'
related:
  - '[[2026-05-13-cli-workflow-redesign-epic-plan]]'
---

# `cli-workflow-redesign` W52 Service Contract Code Review

W52-SERVICE-001 | HIGH | Per-modelo service accepted whitespace modelo then dispatched raw value
`provider_for_modelo` stripped `modelo`, so values like `" 347 "` were treated as supported. `aggregate_per_modelo` then dispatched using the raw command value. Retenciones could raise a raw `KeyError`; counterpart `" 347 "` could silently route as Modelo 349 and return an incoherent result. Remediated by refusing non-canonical whitespace modelo values before dispatch and adding service tests for the exact failure.

W52-SERVICE-002 | MEDIUM | Result contract did not validate envelope and payload consistency
`PerModeloAggregationResult` allowed mismatched `modelo`, `period`, `provider`, and aggregation payload type. Remediated by adding Pydantic result validation for aggregation modelo, period, and provider/payload type coherence.

W52-SERVICE-003 | HIGH | Persistence/provider adapter row was marked closed without implementation
`S1534` requires persistence, bucket events, registry data, or provider adapters for per-modelo aggregation. The current service intentionally accepts already-materialized observations and does not expose registry binding providers or persistence adapters. Remediated by reopening `S1534` and `S1550`; those rows remain future work rather than fake provider wiring.
