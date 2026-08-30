---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-30'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:c542daf703f235fdf0279a19d491cd0a7947c8f39cfb93013a0a3b4a3f278287'
step_id: 'S103'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Derive the binding and casilla length bounds quoted in CLI refusals from the types that enforce them, replacing literals that were only ever printed and so could drift undetected

## Scope

- `src/cadrumo/entrypoints/cli/_modelo_cli_support.py`

## Changes

- `M` `src/cadrumo/domain/iva_compensation/balance.py`
- `M` `src/cadrumo/entrypoints/cli/_modelo_iva_wallet_payloads.py`
- `M` `src/cadrumo/entrypoints/cli/_modelo_payloads_m036.py`
- `M` `src/cadrumo/entrypoints/cli/tests/test_cli_payload_constraint_authority.py`
- `verify:` `pytest src/cadrumo/domain/iva_compensation -n 0 -m ""` -> `pass`

## Notes

The expiry-year bound is deliberately wider than a filing year, because the
value is derived as `source_filing_year + 4`; that reasoning is now recorded on
the alias rather than implied by a bare literal. Probed rather than restated:
2200 accepts, 2201 and 1999 refuse, None accepts.

The M036 event id ran the other way again -- the payload declared a looser
`1..128` string where the model it projects declares `BucketEventId`, a 64-char
hex. Tightening it aligns the projection with the only values its source
produces.
