---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-30'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:6c9e218c6ba03e32303d9ce78c45f21f69a8b52ee1e13416fdaa50c721fba6e8'
step_id: 'S119'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Adopt ModeloCode on the aggregation contract and result payloads, leaving the operator-input command untyped so its registry-driven refusal can still name the supported set

## Scope

- `src/cadrumo/application/aggregation/_service.py`
- `src/cadrumo/entrypoints/cli/_modelo_payloads.py`

## Changes

- `M` `src/cadrumo/application/aggregation/_service.py`
- `M` `src/cadrumo/entrypoints/cli/_modelo_payloads.py`
- `verify:` `pytest src/cadrumo/application/aggregation -n 0 -m unit` -> `pass` (1052; one peer registry failure)
- `verify:` `pytest src/cadrumo/application/aggregation/tests/test_per_modelo_service.py -n 0 -m ""` -> `pass` (23)

## Notes

Three sites declared the same modelo bound, two of them on the canonical side.
Adopting the validated type on all three broke a test asserting that a
whitespace-padded code is refused at DISPATCH with a message naming the
supported modelos.

That test pins a deliberate design rather than an oversight: which modelos the
service supports is registry-driven, and the CLI contract allows a late refusal
for exactly that reason provided it lists the accepted set. Typing the command
field refused earlier with a generic shape error and lost the listing, so the
command field keeps its own shape and now says why. The contract and result
models, which carry no operator input, took the canonical type.
