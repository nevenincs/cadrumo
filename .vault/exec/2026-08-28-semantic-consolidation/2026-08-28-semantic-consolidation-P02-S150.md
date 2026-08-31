---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:d955322a806c2247cba6a890dab0953b8e4d2b576a07b3c22f0dc105348b9b64'
step_id: 'S150'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Gate the country-code field class, and fix the key collision that made both class gates blind to every field name a module declares more than once

## Scope

- `src/cadrumo/core/tests/test_country_code_fields_use_one_annotation.py`
- `src/cadrumo/core/tests/test_currency_fields_use_one_annotation.py`
- `src/cadrumo/domain/calculations/registry/donativo_bindings.py`
- `src/cadrumo/application/modelo/operation_definitions.py`

## Changes

- `A` `src/cadrumo/core/tests/test_country_code_fields_use_one_annotation.py`
- `M` `src/cadrumo/core/tests/test_currency_fields_use_one_annotation.py`
- `M` `src/cadrumo/domain/calculations/registry/donativo_bindings.py`
- `M` `src/cadrumo/application/modelo/operation_definitions.py`
- `verify:` `pytest both class gates -n 0 -m ""` -> pass (10)
- `verify:` `pytest registry -k donativo` -> pass (9); `application/modelo -k operation` -> pass (85)
- `verify:` mutation probe, four arms, all RED after the collision fix; BLIND on one arm before it

## Notes

Two sites the census called plainly adoptable were byte-identical to the
canonical and just not importing it. Verifying before acting caught something the
census had missed on one of them: `donativo_bindings` also applies the shared
`uppercase_alpha_code` validator, so its annotation carries the LENGTH and the
validator carries the CASE policy. Adopting the length-only canonical preserves
behaviour exactly, which it would not have if the case rule had lived in the
annotation.

The country gate deliberately checks the SHAPE only. Unlike currency, this class
has a live policy split that is defended on both sides --
`normalise_iso_3166_alpha2_jurisdiction` refuses a lowercase token because the
jurisdiction axis selects regulatory treatment, `validate_country_code` folds it
because a counterparty's country is a label. Sharing the shape stops a third
length bound appearing; keeping the policies separate stops a de-duplication
silently moving one site onto the other's regime.

### The gates were blind and the probe found it

The first probe run reported the hand-spelled-bound arm GREEN. The cause was in
my own gate: `found[f"{path}::{field}"] = annotation` keyed a dict by field name,
so a module declaring the same name twice kept only one entry.
`operation_definitions.py` declares `pais` at two lines and `codigo_pais` at two
more, so the mutation landed on a declaration the gate then overwrote.

The currency gate shipped with the identical flaw. Five modules declare a
currency field name more than once and `application/ledger/models.py` does it
FOUR times, so that gate could see one of four and said nothing about the rest.
Both now map a site to the SET of annotations declared under it, and a site
offends when any member is non-canonical. The key stays `path::field` rather than
gaining a line number, because an exception keyed by line goes stale on the next
edit above it.

This is the count-without-members failure in a new costume: a lookup keyed by
something non-unique reports a real number about the wrong population.
