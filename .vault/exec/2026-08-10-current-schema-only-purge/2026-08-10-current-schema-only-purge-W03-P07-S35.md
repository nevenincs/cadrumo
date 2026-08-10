---
tags:
  - '#exec'
  - '#current-schema-only-purge'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:69015ffa1a7f4b6fe0d4e1580241f4e6b6c1beccd7cd2ad0cc840bdd713f46e6'
step_id: 'S35'
related:
  - "[[2026-08-10-current-schema-only-purge-plan]]"
---

# Select the Modelo 303 recurrence producer before the work, not after it

## Scope

- `src/cadrumo/application/calculations/_iva_wallet_reconciliation.py`
- `src/cadrumo/application/calculations/tests/test_iva_wallet_reconciliation.py`

## Description

- Call the generic recurrence reconstruction only when the caller has asked for it.
- Return an empty prefill report when it is switched off, so a disabled producer contributes neither a value nor a report.
- State the new contract on the selecting flag.
- Add a regression whose positive control is the adjacent test that proves the enabled behaviour.

## Outcome

Landed in `01d5567ce4`. The remedy is REORDER, not collapse.

Two producers built the same recurrence carrier and a boolean chose between
them, but the choice was read AFTER the generic one had already run. On the
strict path its recurrence was discarded while its prefill report still rode out
on the returned reconciliation report, so a producer the caller had switched off
went on shaping the artefact the caller received. The switch turned off the
value and not the influence. It also spent a repository read and a full history
reconstruction on the one path that had just declared that producer must have no
authority.

Substitutability was measured before the shape was chosen, because collapsing
two resolvers with different contracts is how the widening trap is sprung. The
generic reconstruction reads the compensation history and the generic
previous-filing gather and accepts legacy envelopes by design. The strict
resolver additionally requires exact requirement resolution, a filing-year and
period match, a non-refused revision, a fixed-point normalised disposition-aware
envelope, and the available-compensation casilla. The strict one refuses what
the generic one accepts, so they are not substitutable and only the ordering
could move.

The report shape was safe to empty because its consumers were counted first:
exactly one reference outside the owning module, in a test that exercises the
enabled path and is unaffected. No production consumer reads it.

## Notes

The regression asserts the observable consequence, an empty report, rather than
that the extractor was never invoked. There is no way to assert non-invocation
here without a mock, and a real consequence is worth more than a spy. The gap is
stated rather than implied: a future change that stopped calling the extractor
but still published a populated report would pass this test.

The test went into the calculations package rather than beside the existing
prefill-report assertion, because that module was carrying another campaign's
uncommitted work. The calculations package is also the narrower owning package
for the changed file, so the constraint and the correct home agreed.

Found by semantic sweep rather than by name. A grep for the carrier type finds
both producers only if the reader already suspects there are two.
