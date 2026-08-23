---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:2336f81cd6b608dc0b13c8d82a7bd33147537ce154256568268dee73ee40c8e0'
step_id: 'S13'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

# enumerate exported calculation helpers and explicit readiness declarations

## Scope

- `dev/source_connectivity/discovery.py`

## Description

- Derive the exported domain symbol set from package declarations.
- Discover typed exported helpers that structurally perform arithmetic or aggregation.
- Discover explicit readiness constructors carrying both `ready` and `source_kind` axes.

## Outcome

The census now detects calculation-capable helper surfaces and explicit source-readiness declarations independently. Helpers remain candidates rather than mappings; readiness remains evidence rather than resolver enrollment.

## Notes

Ruff passed. The live scan found both inventory variation helpers, finca annual aggregation, amortization computation, and exactly the explicit inventory and fincas readiness declarations. The broad helper inventory is intentionally classified later by the canonical census rather than narrowed by a domain-name allowlist.
