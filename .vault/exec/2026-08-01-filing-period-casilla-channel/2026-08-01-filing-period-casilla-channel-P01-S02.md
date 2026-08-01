---
tags:
  - '#exec'
  - '#filing-period-casilla-channel'
date: '2026-08-01'
modified: '2026-08-01'
body_schema: 'body-v1'
body_hash: 'sha256:ac8acb2624fc3fb3b06f0c12d949ebd9b369b2eaa243814039907de488452ffd'
step_id: 'S02'
related:
  - "[[2026-08-01-filing-period-casilla-channel-plan]]"
---

# Supply period.registry_token for the filing_period semantic role on the string channel, keeping filing_year on the Decimal channel

## Scope

- `src/cadrumo/application/modelo/_binding_resolution.py`

## Description

- Add a frozen `DeclarationPeriodInputs` carrier holding a Decimal `casilla_inputs` channel and a string `text_casilla_inputs` channel.
- Fill the `filing_period` semantic role with the canonical `Period.registry_token`, on the string channel.
- Keep the `filing_year` role on the Decimal channel, its registry `data_type` being int-family `year`.
- Remove the ordinal projection and the refusal it raised for periods carrying no ordinal.

## Outcome

The informational period casilla now carries the AEAT token the registry declares it accepts. Its `data_type` is `period_code`, whose validator admits exactly the AEAT forms, and its label names the quarterly set outright.

The token is the only representation total over every declared period form. The retired ordinal projection returned nothing for extended, event and ad-hoc periods, and for the fourth instalment code, which made the extended OSS quarters structurally inexpressible. A new test asserts the ordinal is absent for an extended quarter while the token resolves, so the improvement is gated rather than asserted.

All thirteen registry declarations of the `filing_period` semantic role were checked, across eight modelos. Every one declares `data_type = "period_code"`, so no revision routes this role to a numeric channel and the change is uniform.

## Notes

This Step removes the sole production consumer of the period ordinal projection. Retiring the projection itself belongs to a later phase and was deliberately left undone here, per the dispatch scope. A search of the committed tree confirms zero production consumers remain, only the property definition in `src/cadrumo/core/_period.py`, so that retirement needs no consumer sweep.
