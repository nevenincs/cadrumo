---
tags:
  - '#exec'
  - '#live-iva-compensation-wallet'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S68'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
---

# W08.P19.S68 repository-backed filing-history regression

Scope: Execute W08.P19.S68 from the live IVA compensation wallet plan.

## Description

- Merge same-period ordinary calculation observations and secure IVA-history projections before previous-filing binding resolution.
- Preserve source kind per casilla so mixed observations keep compensation provenance separate from ordinary filing totals.
- Project generated IVA compensation from secure history into the previous-filing resolver contract.
- Correct Modelo 390 casilla 97 binding to source the final period's generated compensation instead of end-of-period available balance.
- Add full Modelo 390 snapshot coverage proving ordinary 303 annual total bindings resolve from local filing observations while compensation bindings resolve from secure IVA-history observations for the same periods.
- Add three-year repository-backed filed-history coverage that persists sanitized Modelo 303 observations, reloads them, and uses the production carry-forward projector.
- Review the S68 slice and record the resolved mixed-source finding in the rolling audit.

## Outcome

S68 non-private calculation coverage is complete. The full Modelo 390 mixed-source resolver path now has repository-backed coverage, and the calculation-layer filed-history repository now has three-year stored/reloaded carry-forward coverage without private taxpayer fixtures.

Verification passed for the focused mixed-source regression, focused three-year repository regression, the broader IVA compensation history plus Modelo 390 continuity gate, ruff, locale audit, private/live constant scan, and test-shortcut scan.

## Notes

Live cross-year read-only AEAT verification remains open under W06.P15.S56. No live AEAT filing, payment, confirmation, represented-taxpayer selection, or other write path was executed.
