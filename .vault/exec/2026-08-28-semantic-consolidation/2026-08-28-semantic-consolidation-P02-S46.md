---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:0bd05dc1405fc30f96357d5bc8e4d5a9959fa3c3a382d64a3589f3bfecb024c5'
step_id: 'S46'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Rule on the currency pattern once for both the invoice and export-row payloads, given the canonical already normalises to uppercase at the parse boundary

## Scope

- `src/cadrumo/`

## Changes

- `verify:` every currency field on the invoice and export-row payloads reads `IsoCurrencyCode`
- `verify:` `core/tests/test_currency_fields_use_one_annotation.py` holds the ruling structurally

## Notes

Closed by work recorded under S129, S144, S145 and S147. The step asked for ONE
ruling covering both payload families; what it got is a ruling plus a gate,
because the manual search kept succeeding -- four consecutive rounds each found a
currency declaration the previous round had missed, and four policies were live
at once disagreeing on `"eur"`, `" EUR "` and `"12A"`.

The ruling is `IsoCurrencyCode`: trim, uppercase, three letters. Three sites
carry a declared exception with its reason -- a registry-authored declaration
that should fail its author rather than be repaired, a boundary that already
applies the canonical policy through a `mode="before"` validator, and a
`Literal['EUR']` that is stricter rather than looser.

Marked complete on verification rather than on memory: the step was open while
the work was done, which is the state this campaign has now found several times.
