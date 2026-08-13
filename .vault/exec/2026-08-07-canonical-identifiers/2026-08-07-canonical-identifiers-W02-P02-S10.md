---
tags:
  - '#exec'
  - '#canonical-identifiers'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:b380f2877da8708760eec074aa74a984caab5627e89adc966cd9deced7a52007'
step_id: 'S10'
related:
  - "[[2026-08-07-canonical-identifiers-plan]]"
---

# Add the strict roundtrip and anti-tautology proof for the discriminated pair. Populate every defaultable field on IvaCompensationPeriodState non-default, push it through the real encrypted repository and assert strict model equality on load. For the anti-tautology proof delete the persisted provenance field from the on-disk payload, reload through the real production read path, and assert refusal rather than a silent re-default. Add a companion case proving the cross-field validator refuses both impossible pairs, an operator-seeded row carrying an expediente and an AEAT-capture row carrying none

## Scope

- `src/cadrumo/domain/iva_compensation/tests/`

## Description

- Verify the existing strict encrypted-repository roundtrip against the live
  discriminator and populate every defaultable field away from its default.
- Replace the in-memory deletion with an authenticated encrypted-row mutation:
  remove stored `payload.provenance`, then reload through
  `IvaCompensationHistoryRepository` and assert the precise missing-field
  refusal.
- Assert both prohibited provenance-expediente pairings expose their
  cross-field validator reason.
- Run the focused test, Ruff, formatter, Ty, and formal review.

## Outcome

The proof now exercises the actual encrypted persistence boundary. The focused
suite passed all 10 tests; Ruff, formatting, Ty, and formal review passed with
no findings.

## Notes

The earlier test file existed from the S09 commit but its anti-tautology case
only validated an in-memory model dump. This Step replaces that insufficient
proof with the production read path. W02.P02.S65 remains open as the separate
legitimate-population control required before the discriminated-pair release
condition is met.

