---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:42fa75f6fc40d405db11df2531c89ff5c5fc5fc9df2c1315cea3317a4e4122b4'
step_id: 'S22'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

# classify each of the five deferred row sources as an independent candidate

## Scope

- `src/cadrumo/_data/source_connectivity/census.toml`

## Description

- Create independent rows for related-party, refund, donor, gasto-193 contributor, and withholding-296 capabilities.
- Classify the four families with existing registry bindings as ingress-blocked.
- Classify withholding-296 as registry-blocked because current Modelo 296 declares relation-prefill bindings only.
- Attach separate assembler evidence, destinations, review conditions, expiry, owners, and bounded follow-ups.

## Outcome

All five deferred row families are individually actionable instead of sharing a blanket deferral. The census preserves the currently different blocking boundary for withholding-296 rather than inheriting an outdated claim that all five already have registry bindings.

## Notes

The strict bundled loader passed. A current authoring-tree regex sentinel confirmed zero `source = "withholding296"` declarations under Modelo 296; the other four families have live source bindings in Modelos 232, 360, 182, and 193 respectively.
