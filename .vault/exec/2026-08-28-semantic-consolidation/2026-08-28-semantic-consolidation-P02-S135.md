---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:7ec6f473632776def143c06e9a4370dc1d6e0d14e9ca24f35fb880728379f97c'
step_id: 'S135'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Declare the ISO alpha-2 shape once and record at each site whether it folds or refuses a lowercase token, leaving that policy question open rather than settling it by consolidation

## Scope

- `src/cadrumo/core/country_code.py`
- `src/cadrumo/domain/invoices/validators.py`
- `src/cadrumo/domain/calculations/registry/schema_scalars.py`

## Changes

- `M` `src/cadrumo/core/country_code.py`
- `M` `src/cadrumo/domain/invoices/validators.py`
- `M` `src/cadrumo/domain/calculations/registry/schema_scalars.py`
- `verify:` probed both surfaces on `ES` / `es` / `" ES "` / `E1`; behaviour unchanged at each

## Notes

Reported as a two-way divergence: the invoice validator normalises then matches,
the registry one matches the raw value, so `"es"` splits them. There is a THIRD,
and it changes the verdict. `normalise_iso_3166_alpha2_jurisdiction` in
`core/parsing/_codes.py` also refuses a lowercase token, and refuses it ON
PURPOSE -- its docstring says the jurisdiction axis selects a row's
regulatory-source treatment, so a caller supplying `"es"` is told to declare the
canonical code rather than having one guessed.

That makes the recommended fix -- add `.strip().upper()` to the registry copy --
the wrong move. It would have propagated the folding policy into the boundary
whose sibling in core deliberately refuses it, under cover of a de-duplication.

What is genuinely duplicated is the two-character shape, written out as
`^[A-Z]{2}$` at both sites. That is now one named fragment in
`core/country_code.py`, and each caller keeps its own fold-or-refuse answer with
the reason recorded at the site: an invoice counterparty's country is a label, so
folding costs nothing; a casilla's country selects a treatment, so it refuses.

The fold-versus-refuse question across the two surfaces is left OPEN and is
flagged for the operator. Settling it needs evidence about what AEAT accepts on
each surface, which a consolidation pass does not have and must not manufacture.
`core/country_code.py` already declined once to add a charset check on exactly
this reasoning; the same reasoning applies to the case policy.
