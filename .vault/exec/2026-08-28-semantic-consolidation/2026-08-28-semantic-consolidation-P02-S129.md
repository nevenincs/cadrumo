---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-30'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:bbb1f81b6ee1d03b01f1c658123793513d9feb3273ee16b105f5c9d65cb7a6dd'
step_id: 'S129'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Publicise the eliding issue-detail annotation and adopt it at four sites, two of which refused an over-length detail where the canonical deliberately elides

## Scope

- `src/cadrumo/application/ledger/preflight.py`
- `src/cadrumo/application/aggregation/`
- `src/cadrumo/entrypoints/cli/`

## Changes

- `M` `src/cadrumo/application/ledger/preflight.py`
- `M` `src/cadrumo/application/aggregation/_impatriado_income_ledger.py`
- `M` `src/cadrumo/application/aggregation/_irnr_income_ledger.py`
- `M` `src/cadrumo/entrypoints/cli/_ledger_payloads.py`
- `M` `src/cadrumo/entrypoints/cli/_modelo_payloads.py`
- `verify:` `pytest src/cadrumo/application/ledger/tests -k preflight -n 0 -m ""` -> `pass` (39)
- `verify:` `pytest src/cadrumo/application/aggregation/tests -k "impatriado or irnr" -n 0 -m ""` -> `pass` (16)

## Notes

This is a defect, not tidiness. The canonical annotation ELIDES an over-length
detail at 512 rather than refusing it, and the comment above it says why:
refusing "would drop the explanation for the exclusion AND fail the aggregation
that produced it -- a silent under-declaration dressed as a validation error."

Two CLI payloads restated the bound as `Field(min_length=1, max_length=512)`,
which REFUSES. They reintroduced the exact failure the annotation exists to
prevent, one layer further out: a 513-character detail failed the emit and took
the explanation with it.

The annotation itself was also written out three times, once in preflight and
once in each of two aggregation ledgers.

Probed at the CLI payload: a 600-character detail is now accepted and stored at
512, where before it was refused.
