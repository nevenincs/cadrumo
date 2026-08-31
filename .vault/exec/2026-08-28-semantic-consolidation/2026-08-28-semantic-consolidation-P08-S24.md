---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:d5bb6860981a48f166ec78be90b2f1bb7816442e29a3e5c1c7fb6ea1312cd1f4'
step_id: 'S24'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Adjudicate the nine-character tax-id fields against the identity token, which normalises without enforcing a length and so is not a safe promotion

## Scope

- `src/cadrumo/domain/calculations/registry/`

## Changes

- `verify:` six registry fields carry `TaxIdIdentityToken` with the 9-width retained
- `verify:` zero bare `str | None = Field(min_length=9, max_length=9)` tax-id fields remain

## Notes

Settled by S30, whose adjudication is exactly what this step asks for and was
recorded there.

The step's own framing is the answer: the identity token normalises without
enforcing a length, so promoting a nine-character field to it ALONE would have
dropped the width. The six fields therefore carry both -- the token for the
normalisation, the existing `min_length=9, max_length=9` for the width -- rather
than one replacing the other.

The probe that decided it: against the bare bound, the token folds `12345678z`
to uppercase where the bare bound stored it unfolded, and accepts a padded
` 12345678Z ` the bare bound refused because nothing stripped before the length
was measured. Strictly better on every column, and no new refusal, which is what
made it safe without a tax review.

The CHECKSUM question that would have gone further is deliberately still open and
recorded in S30: one of the six says in its own docstring that a previous payer
may be foreign without a Spanish NIF, which no Spanish control character can
validate.
