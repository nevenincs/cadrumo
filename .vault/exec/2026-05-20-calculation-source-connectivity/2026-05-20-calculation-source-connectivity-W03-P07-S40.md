---
tags:
  - '#exec'
  - '#calculation-source-connectivity'
date: '2026-07-04'
modified: '2026-07-08'
step_id: 'S40'
related:
  - "[[2026-05-20-calculation-source-connectivity-plan]]"
---

# Define fincas resolver adapter boundaries without enrolling calculations

## Scope

- `src/aeat/application/aggregation/_source_fincas.py`

## Description

Add `application/aggregation/_source_fincas.py`: `FincasSourceReadinessResolver`, which implements the source-mesh resolver shape (`resolver_id`, `owned_sources = ()`, `resolve`) but is NOT enrolled in `merge_source_resolutions`. Its `resolve` reads `fincas_source_readiness()` and returns an empty resolution carrying exactly one `source_domain_not_ready` blocked-readiness diagnostic. Add the `source_domain_not_ready` member to the `CalculationSourceDiagnosticReason` Literal.

## Outcome

The fincas source surface is provisioned as a resolver-adapter boundary that refuses visibly and enrolls nothing (owns no `BindingSourceKind`). Landed in commit `7c15ee0184`. Gates clean.

## Notes

The resolver is deliberately absent from the live mesh tuple; the `fincas` diagnostic `source_kind` is a free string, not a `BindingSourceKind` member, so it cannot enter the enrolled/deferred/reserved source sets and cannot silently blank a calculation.
