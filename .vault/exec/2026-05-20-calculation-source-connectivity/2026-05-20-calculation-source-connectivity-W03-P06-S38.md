---
tags:
  - '#exec'
  - '#calculation-source-connectivity'
date: '2026-07-04'
modified: '2026-07-08'
step_id: 'S38'
related:
  - "[[2026-05-20-calculation-source-connectivity-plan]]"
---

# Test region scoped category profiles select by profile CCAA

## Scope

- `src/aeat/application/aggregation/test_renta_ledger_region.py`

## Description

Add a domain unit test pinning all four `select_deductibility_profile` branches (no override, override selected by matching comunidad, override for a different comunidad falls through to state, override with undeclared residence returns fail-closed). Add application tests: `test_region_override_selected_when_residence_matches` (a synthetic per-comunidad override halves the deductible versus the full-deductible state profile) and `test_region_override_undeclared_residence_fails_closed` (emits `REGION_UNDECLARED_FOR_OVERRIDE`, no observation).

## Outcome

Proves selection-by-comunidad and the D4 fail-closed refusal using a SYNTHETIC test override (never a real regime figure). 30 tests passed across the domain and application layers. Landed in commit `1ca532e93a`. Gates green.

## Notes

Implements the S38 test and decision D4 of ADR `2026-07-04-renta-region-deductibility`. The override profile is a test double for the selection mechanism; no regulated deductibility value is asserted, satisfying the no-tautological-calculation-tests discipline.

Sibling step S36 (derive the residence comunidad from the active `TaxResidenceProfile` inside the aggregation) is intentionally LEFT OPEN / deferred. A best-effort profile read was prototyped and proven (guarded, byte-identical, tests green) but backed out at coordinator direction: it adds a profile-load and failure surface to the hot aggregation path for a field that is inert while the override layer is empty, and the cleaner shape is caller-side wiring introduced when a real territorial-regime override is first populated. The ADR remains `proposed`; these records document the proposed design the landed mechanism implements.
