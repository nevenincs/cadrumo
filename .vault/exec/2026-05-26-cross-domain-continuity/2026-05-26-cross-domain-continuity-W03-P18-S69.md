---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-10'
modified: '2026-07-10'
step_id: 'S69'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
  - "[[2026-07-10-cross-domain-continuity-audit]]"
---

# re-run round-6 Joan SL persona to confirm every B-JOAN-* finding closed

## Scope

- `plus fresh sociedad-anonima persona`
- `.vault/audit/`

## Description

- Re-run the Joan S.L. persona in an isolated encrypted store for Modelo 200 2024/2025 and Modelo 202.
- Create a distinct high-INCN sociedad-anónima persona and inspect its Modelo 202 obligation, work, and binding route.
- Confirm corporate calendar coverage and test M200/M202 work creation plus calculation refusals.
- Reconfirm the existing S343 Article 27 finding without duplicating it.

## Outcome

Both corporate personas created and surfaced the expected M200/M202 obligations. The calendar contains M200 2024 and 2025 annual rows plus M202 2025/2026 instalments. The high-INCN S.A. resolves its INCN fact from the profile rather than reporting it missing, creates the Modelo 202 work unit, and fails calculation closed only on the genuine prior-year quota relation with no draft saved. The 2024/2025 M200 and regular S.L. M202 paths similarly name concrete missing bindings and remediation instead of exposing a bracket or template failure.

The prior bare-casilla question now exposes canonical `DP200010:00552` and documents the canonical-ID contract. The existing S343 premature Article 27 payload reappeared during M202 creation and remains separately open. No new BLOCKER or MAJOR corporate defect appeared.

The final fresh Micro PyME S.L. replay reached the historical 2024 formula route through the real CLI. In a separately encrypted local store, `aeat config profile create` created a common-regime legal-entity profile with `legal_entity_form=sl`, `INCN=500000`, `new_entity=false`, and an economic activity. `aeat --format json app modelo work create --modelo 200 --year 2024 --period 0A --revision 2024-y-siguientes` created work unit `a3fcb3c11f5fbb4a697a85982c41c2a4008e4d574b8bbc098dd0c85adb8e54f7`.

`aeat --format json app modelo work calculate` supplied the live oracle inputs from `test_modelo_200_micro_empresa_pyme_cuota_2024`: `00501=100000.00`, zero corrections and reserves, form `sl`, new-entity flag `0`, INCN `500000`, Estado share `100`, zero carry-forward balances, and zero M202 payment relation. It saved draft revision `c3990f60442d4a9cf722e42c99a6b9f79e20913513544a1ac58c7237ef9e98e1`; `DP200014:00562` was `23000.00`, and the JSON payload contained no `bracket_no_window` error.

## Notes

The Micro PyME replay is a real CLI formula oracle rather than a test edit: its expected amount is the 2024 Ley 27/2014 article 29 micro-entity rate, €100,000.00 × 23% = €23,000.00. It closes the historical Modelo 200 2024 bracket/template evidence gap for S69. The existing S343 finding remains outside this proof.
