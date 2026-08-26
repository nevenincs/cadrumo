---
tags:
  - '#audit'
  - '#casilla-schema'
date: '2026-08-12'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:90f0e8e58d8ec25870b54e127e471e5b754d39224dbc9471afce68c1d245b701'
related:
  - "[[2026-08-10-casilla-schema-plan]]"
  - "[[2026-08-10-casilla-schema-blocker-spine-adr]]"
---
# `casilla-schema` audit: `W05.P11.S38 dormant enum adjudication review`

## Scope

Formal review of commit `9070c86e97`, the working S38 export-exemption test, and the S38 execution record. The review covered destructive enum and Literal contraction, old-token and locale removal, action-map totality, compiled registry populations, retained exemption semantics, reconciliation consumption, regression-test bite, and the recorded verification claims.

## Findings

### finding-constructor-gate | medium | The production-constructor gate accepted any qualified enum reference

The first implementation of `test_every_verification_finding_kind_has_a_production_constructor` did not identify `ModeloVerificationFinding` construction. Its AST census accepted every qualified `ModeloVerificationFindingKind.MEMBER` attribute anywhere in production, regardless of context. A member used only in a comparison, branch, secondary projection, or other non-producing reference could therefore satisfy the gate while remaining impossible to construct. The current five retained members had independently observed constructors, so this was a regression-proof defect rather than evidence that either deletion was wrong.

## Recommendations

Resolved. The structural gate now derives the imported production constructor and enum identities, resolves their direct import aliases, visits only actual `ModeloVerificationFinding` calls, and requires exactly one recognized literal enum member in `kind=`. Its separate producer-set equality assertion covers all enum identities. An adversarial source probe proves that a branch-only `BLOCKING_RULE` reference does not count while an `ADVISORY` constructor does.

No change is recommended to the adjudication decisions. `profile_schedule`, `UNRESOLVED_BINDING`, and `INVALID_WAIVER` had zero pre-deletion production/data consumers outside their owners, total projection, fixtures, and locale leaves; the current tree contains no legacy token admission. The remaining finding action map is total at import. `PRE_POPULATED_BY_AEAT` is honestly dormant: compiled authority has zero declarations and every Modelo 100 revision has no fixed-width layout, so the guard will red if that transport precondition changes.

The compiled FEEDS census is real and exact at the stated grain: 17 M303 declarations across six revisions, distributed 2 in `2009-y-siguientes` and 3 in each later named revision. Twelve declarations are verification-enrolled semantic totals and none is directly extractable; the reconciliation consumer excludes export-exempt computed ids while retaining the observable numbered-box comparisons. The five `iva.autoconsumo.promotor.cuota` declarations are not verification-enrolled, so the consumer does not pretend to reconcile them. The false-claim mutation still exercises validator refusal, and the compiled census reds on member removal or addition.

## Resolution

The medium finding is **resolved**. Independent execution of the collector found exactly `ADVISORY`, `BLOCKING_RULE`, `CROSS_PERIOD_DEPENDENCY_UNCLEAN`, `MISSING_REQUIRED_CASILLA`, and `RECONCILIATION_MISMATCH`, equal to the retained enum membership. A direct-import-alias probe resolved the constructor and enum aliases correctly. Missing, multiple, dynamic, or unrecognized `kind=` values refuse instead of contributing liveness, and a comparison-only member is excluded by the biting regression.

Final bounded gates passed: the complete action-projection module reported 3 passed; Ruff lint and format checks were clean; BasedPyright reported zero errors, warnings, or notes; and the scoped diff check was clean.

Final verdict: **PASS**. The four S38 adjudication decisions, destructive compatibility posture, retained exemption evidence, canonical action-map totality, constructor-liveness proof, and execution record are all supported by the current tree. No S38 finding remains open.
