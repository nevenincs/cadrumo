---
tags:
  - '#audit'
  - '#ledger-hardening-close'
date: '2026-06-11'
modified: '2026-06-11'
related:
  - '[[2026-06-10-ledger-interface-contract-plan]]'
  - '[[2026-06-10-ledger-invoice-unification-plan]]'
---



# `ledger-hardening-close` audit: `ledger hardening close honesty review`

## Scope

Fresh inherited-state review of the ledger hardening epic close after the C5 remainder and deferred CLI verification sweep. Reviewed the C1-C7 handover claims, the C5 and C4 Vault plans, the current code/test surface, and the latest verification results before any claim of structural completion.

## Findings

### HIGH - C4 is not structurally complete because `AggregationSourceKind.INVOICE` retirement remains open

The unified invoice CLI is implemented and verified, but the C4 plan now honestly stands at 23/30. Open steps are `S01` and `S19` through `S24`: consumer search and the registry-validation reconciliation required before deleting `AggregationSourceKind.INVOICE`. Source search shows live registry validation consumers in `_bindings.py`, `_schema.py`, `_validate_record_sections.py`, `_retenciones.py`, and multiple registry tests. Full registry collection is also currently red from unrelated peer registry and wizard refactor errors, so this is not a safe deletion in this close pass.

Tracking: the open C4 steps remain in `2026-06-10-ledger-invoice-unification-plan`; no duplicate step was created.

### MEDIUM - Full-tree gates are still blocked by unrelated factory work

Feature-scoped ledger gates are green. Repository-wide Vault and registry checks are not green because of unrelated peer work: the Vault structure check reports the live-censo exec filename violation, and registry collection fails on wizard/profile-key registration plus in-flight registry support symbol errors. These failures were reproduced during close review and are outside the committed C5/C4 tracking surface.

Tracking: recorded here as close residual risk; not converted to ledger steps because the affected plans and files belong to other active campaigns.

### LOW - C5 plan tracking was stale and is now reconciled

C5 implementation existed but the plan previously showed 13/32 complete and lacked exec records for several already-checked steps. The close pass added C5 exec records, fixed the timestamp no-legacy gap, and closed the C5 plan at 32/32 with focused code, type-surface, conformance, and Vault checks.

### LOW - C4 plan tracking was stale and is now partially reconciled

C4 implementation evidence existed while the plan showed 0/30. The close pass added reconciliation exec records and closed the verified unified-invoice steps only. The plan remains intentionally open for the registry alias retirement chain.

## Recommendations

- Treat the ledger hardening epic as verification-complete for C5 and the unified invoice CLI, but not structurally complete for C4 alias retirement.
- Execute a dedicated registry-validation reconciliation for `AggregationSourceKind.INVOICE` once peer registry collection stabilises. The acceptance gate is deletion of the enum member plus green registry collection and affected aggregation/operator tests.
- Keep using the two-lane CLI gate set for ledger close checks: default plus `-m integration`, with documented-command and JSON schema conformance included.
- Do not claim full campaign closure while the C4 plan has open steps; refer to this audit when handing off the remaining registry-retirement work.

## Codification candidates

- **Source:** HIGH finding above. **Rule slug:** `retired-enum-members-need-consumer-reconciliation`. **Rule:** Before deleting a retired enum member, reconcile every validation, schema, fixture, and test consumer into one accept-or-reject state and prove the owning collection gate is green.
- **Source:** LOW C5 tracking finding. **Rule slug:** `plan-closure-requires-exec-records`. **Rule:** A plan step must not be marked complete unless a matching exec record exists or the close audit explicitly records why the step is only a deferred carry-forward.
