---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-30'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:c99dfb3fe36254269d7d9a70e9efc5565fbd7090b881dee8f6e63f46c8f807dc'
step_id: 'S126'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Declare the ISO 4217 currency shape once as a normalising alias and adopt it at the domain model and both CLI payloads, giving the domain the uppercase rule it lacked

## Scope

- `src/cadrumo/core/parsing/`
- `src/cadrumo/domain/currency/`
- `src/cadrumo/entrypoints/cli/`

## Changes

- `M` `src/cadrumo/core/parsing/_codes.py`
- `M` `src/cadrumo/core/parsing/__init__.py`
- `M` `src/cadrumo/domain/currency/models.py`
- `M` `src/cadrumo/entrypoints/cli/_ledger_catalogue_invoice_payloads.py`
- `M` `src/cadrumo/entrypoints/cli/_ledger_payloads.py`
- `verify:` `pytest src/cadrumo/domain/currency src/cadrumo/core/parsing -n 0 -m ""` -> `pass` (46)
- `verify:` `pytest src/cadrumo/adapters/inbound/financial -n 0 -m ""` -> `pass`

## Notes

Three sites, three different strengths for one concept. The domain model bounded
the length only, so it accepted `eur` and `$$$`; two CLI payloads carried
hand-rolled `^[A-Z]{3}$` patterns, stricter than the model they project.

The canonical normaliser already existed and its docstring already warned why a
field constraint is the wrong shape: a `min_length` / `max_length` bound fires on
padding first and never reaches the normaliser, so `" usd "` is refused for its
spaces rather than accepted as `USD`. The domain model had fallen into exactly
that trap. The alias is a `BeforeValidator` for that reason.

Probed at the domain model: `" usd "` now yields `USD`, and a two-letter code
refuses.
