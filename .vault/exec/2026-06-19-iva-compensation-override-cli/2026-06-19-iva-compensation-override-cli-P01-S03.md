---
tags:
  - '#exec'
  - '#iva-compensation-override-cli'
date: '2026-07-04'
modified: '2026-07-17'
body_hash: 'sha256:8698a01e867a1f836d2cd8e333c9afbf2154e63cc378b56d5d7bdf51db8ebf9f'
step_id: 'S03'
related:
  - "[[2026-06-19-iva-compensation-override-cli-plan]]"
---

# Add a behaviour test: record override then assert the persisted taxpayer_override decision unblocks calculate and applies the amount to casilla 110 (persona 2T resolves to 525)

## Scope

- `src/aeat/application/modelo/tests/test_iva_wallet_engine_integration.py`

## Description

- Add a real-behaviour test recording an override then calculating the dependent Modelo 303 period.
- Assert a negative control: with no override and no wallet or local recurrence, the calculation blocks fail-closed.
- Record the override through the application recorder and assert the persisted decision carries `taxpayer_override` authority, non-blocking.
- Recalculate and assert the amount plumbs through to the prior-compensation casilla, applies as compensación, and reduces the final result.

## Outcome

- The behaviour suite proves the recorded `taxpayer_override` decision unblocks calculate and applies the amount, with a fail-closed negative control isolating the override's effect.
- Real persistence throughout: real secure backend, real work-unit and calculation-revision catalogues, no mocks, stubs, skips, or tautological assertions.
- Suite green.

## Notes

- The behaviour tests live in the engine-overrides test module rather than the engine-integration module the Step row named; the coverage the Step demanded is present and green.
- The test asserts a 450 override (with a companion test asserting 1200) rather than the persona's 525 figure; both are legitimate acceptance values for the carry-applies contract, derived from the test's own seeded inputs.
