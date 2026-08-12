---
tags:
  - '#exec'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-10'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:e4db01913a161ef2de4966a810eb9d096f95be37487d278a49cb7291d605338e'
step_id: 'S56'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---
# Add one typed ordered evidence-bearing Modelo 303 exonerado-390 activity-row owner for all six activity-code and IAE pairs, reuse S58's nominal filing-evidence references, thread it through value arrival and projection, and delete raw marker, producer-reference, scalar-slot, and placeholder authority

## Scope

- `src/cadrumo/application/filing/`
- `src/cadrumo/domain/calculations/registry/`

## Description

- Define frozen, typed six-row `codigo_actividad` and `epigrafe_iae` evidence with one nominal reference per pair.
- Require every applicable filing to carry slots 1 through 6 in intrinsic order and an evidenced Modelo 347 decision.
- Resolve the active record-design source inside the filing error-translation boundary and project the real `DP30304` source fields in source order.
- Cover exact five-epoch values, both Modelo 347 states, persistence, omitted evidence, invalid row shapes, non-applicability, and wrong source/year refusal.

## Outcome

Independent formal review approved the amended S56 candidate with zero unresolved critical, high, or medium findings. The owner deliberately does not introduce the later `FilingProjectionRef` authority owned by S57.

## Notes

The initial candidate exposed one high stale-census defect in the M303 export applicability gate; the amended AST-backed canonical-owner census and preserved retired-symbol census passed the locked selector. An initial type-check invocation used the clone's incomplete environment and produced cascading missing-import diagnostics; the configured managed interpreter reports zero diagnostics. The plan closure follows this approved audit through the Vault CLI.
