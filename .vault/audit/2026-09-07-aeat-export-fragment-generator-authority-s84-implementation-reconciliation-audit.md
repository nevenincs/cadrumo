---
tags:
  - '#audit'
  - '#aeat-export-fragment-generator-authority'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:9b27aaaee22da8f9e7682aeb8f9e02750c4e3fc4989c44b99a521d81f0017685'
related:
  - "[[2026-07-01-modelo-303-regimen-simplificado-adr]]"
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
  - "[[2026-08-14-modelo-303-regimen-simplificado-s84-immutable-annual-summary-handoff-review-audit]]"
---
# `aeat-export-fragment-generator-authority` audit: `S84 implementation reconciliation`

## Scope

Reconcile the open S84 plan row against the typed handoff implementation that landed across the 2026-08-14 commits, its later public-module relocations, the accepted Modelo 303 simplified-regime decision, and the existing independent design review. The review covers the exact ten-value mapping, source and target calculation identity, filed-current source selection, evidence and digest custody, persistence identity, selection-only Modelo 390 projection, and retirement of the scalar box-79 bridge.

## Findings

### s84-implementation-reconciliation | info | implementation and accepted decision agree

The live resolver consumes one exact filed-and-current Modelo 303 4T calculation revision and assembles the immutable handoff carried by the Modelo 390 0A calculation revision. The domain payload retains source and target work-unit, revision, registry, filing-year, period, evidence, result-digest, and handoff-digest identity. The four Modelo 390 revisions declare the same ten typed endpoints for boxes 74 through 83. Registry gates retain the retired scalar relation and binding identifiers as negative assertions, so box 79 has no second arrival path.

The plan scope was stale after public-module relocations. It now names the current domain/modelos and application/modelo owners instead of the retired filing-only location. This is bookkeeping reconciliation, not a new architecture decision.

### s84-focused-verification | info | current contracts pass after test expectation repair

The registry binding and handoff inventory slice passed four tests without measured-path drift. Strict BasedPyright reported zero errors, warnings, or notes across the handoff types, resolver, binding compiler, and core projection reference. The application handoff suite initially exposed three stale test assertions: one read the retired CalculationSourceRef.binding_source name, and two expected an unwrapped Pydantic ValidationError below the persistence boundary. The assertions were aligned to the current resolved source identity and typed CalculationRevisionPersistenceError contract; the full application handoff module then passed.

No cast, Any annotation, type ignore, Pyright ignore, matcher relaxation, compatibility alias, or fallback was introduced.

## Recommendations

Close W04.P07.S84 as implemented and reviewed. The temporal-coverage S32 row may now consume the existing consolidated per-epoch proof and close its separate yearless in-file enrolment detection gap.
