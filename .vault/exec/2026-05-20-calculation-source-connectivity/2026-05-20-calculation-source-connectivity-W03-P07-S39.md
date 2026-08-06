---
tags:
  - '#exec'
  - '#calculation-source-connectivity'
date: '2026-07-04'
modified: '2026-07-17'
body_hash: 'sha256:5c74ac6fc87d6d9786c45fc130e272115747f082a2a26ab9a7358c5a54ad7f20'
step_id: 'S39'
related:
  - "[[2026-05-20-calculation-source-connectivity-plan]]"
---

# Define fincas calculation source readiness diagnostics

## Scope

- `src/aeat/domain/fincas/_source_readiness.py`

## Description

Add `domain/fincas/_source_readiness.py`: a pure-domain `FincasSourceReadiness` (strict-frozen `ready` / `source_kind` / `reason`) and a `fincas_source_readiness()` returning `ready = False`, because the fincas rendimiento and amortization aggregates are not persisted through the canonical secure-storage revision boundary. Export the surface from the fincas package facade.

## Outcome

The fincas calculation-source readiness is a context-independent domain fact the aggregation resolver reads. Landed in commit `7c15ee0184`. Gates clean.

## Notes

Implements the fincas half of the calculation-source-connectivity ADR Phase 8 ("enroll fincas and inventory only after persistence hardening"): the readiness declares fincas NOT ready so the surface refuses visibly rather than resolving a silent blank (`no-dormant-source-resolvers`).
