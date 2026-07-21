---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-10'
modified: '2026-07-10'
step_id: 'S169'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# project-wide grep for every period-token-handling function produce coverage matrix

## Scope

- `if more than one site survives Wave 1 append Steps to converge`
- `src/aeat/`

## Description

- Grounded the audit in `core/_period.py`, `domain/period.py`, CLI period adapters, the S416 execution record, and semantic code searches.
- Inspected production period construction, boundary, selector, ordering, display, and operator-completion surfaces; classified external and registry selector seams separately from concrete period calculation authority.
- Ran direct runtime probes for a monthly period and Modelo 202 instalments against core, domain, verification, and filing paths.
- Recorded the discovered verification and filing boundary defects in the rolling audit and appended S424 through S431 for each surviving convergence family.

## Outcome

The canonical contract is `Period(filing_year, bare RegistryPeriodCode)`. S416 correctly delegates contiguous calendar spans to `Period` and retains only the sanctioned Modelo 202 payment-month mapping. The audit found live drift outside that authority: verification uses a month start rather than month end; filing, Sheets pull, and Sheets parity have divergent calculation-date policies; MCP still advertises invalid `ANUAL`; and several semantics-specific raw ordinal, ordering, settlement, and display policies are duplicated.

The direct probe established `03` as 2026-03-31 through core and domain but 2026-03-01 through verification. It also established `1P` and `2P` as 2026-04-30 and 2026-10-31 through domain and verification while filing replay returns 2026-12-31. The plan now contains explicit repair and regression steps rather than treating the Wave-1 unification as complete.

## Notes

Registry selector wildcard matching, period-offset arithmetic, official M349 wire codes, and external parser conversion remain distinct responsibilities; the appended work must not collapse them into generic calendar logic. Existing focused tests include one unrelated M100 binding failure in `application/verification/tests/test_verify.py`; it did not exercise a period path and was not used as audit evidence.
