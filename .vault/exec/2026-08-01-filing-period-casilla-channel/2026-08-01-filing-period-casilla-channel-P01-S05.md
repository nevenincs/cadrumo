---
tags:
  - '#exec'
  - '#filing-period-casilla-channel'
date: '2026-08-01'
modified: '2026-08-01'
body_schema: 'body-v1'
body_hash: 'sha256:e3f149357172124c9086c29c18e4350afced2ba1fdbcd46f6fa3b2e03ae85eab'
step_id: 'S05'
related:
  - "[[2026-08-01-filing-period-casilla-channel-plan]]"
---

# Update the parametrised ordinal pins to assert the token on the string channel

## Scope

- `src/cadrumo/application/modelo/tests/test_declaration_period_binding.py`

## Description

- Re-parametrise the quarterly period test from the four ordinals to the four AEAT tokens.
- Assert the token on the persisted string mapping and pin the Decimal mapping to the engine's structural zero.
- Rewrite the provenance test against the observation's real post-change shape.
- Update the semantic-role resolver test, which pinned the same ordinal one layer down.

## Outcome

The pins now assert the token on the string channel across all four quarters, and additionally pin the Decimal slot to zero. That second assertion is the anti-regression guard rather than incidental detail: reinstating the ordinal fill puts the four ordinals back into the Decimal mapping and fails these tests immediately, which is exactly what the S08 mutation run demonstrated.

The provenance test was rewritten against measured behaviour, not against the predicted behaviour. The governing decision predicted that moving the casilla off the Decimal channel would remove its observation row. Writing that predicted assertion and running it proved the prediction false, and the test now records the true shape - the row persists, grounded, carrying the structural zero, because the engine assigns every non-computed declared casilla a zero when it is absent from the Decimal inputs.

The semantic-role resolver test gained a parametrised token assertion, an explicit assertion that the period casilla is absent from the Decimal channel, and a new case proving an extended OSS quarter resolves a token where the retired ordinal projection resolved nothing.

## Notes

The semantic-role resolver test is outside the single file this Step names. It pinned the same retired ordinal and would have stayed red, so it was updated here rather than deferred. Recorded because the Step's scope line does not mention it.

The provenance correction has consequences beyond this Step, and the amending ruling has since carried them. The tracked follow-up on text-casilla grounding is re-scoped from "typed text casillas carry no observation" to "the observation channel emits a structurally wrong Decimal zero for text-family casillas and cannot express their real value". The ruling's reading is sharper than the one reported from execution: the emitted zero is worse than an absence would be, because a structural zero on a period casilla is a plausible-looking wrong value where an absence would at least read as a gap.
