---
tags:
  - '#exec'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:d1fb3460296078ff88bdbd4e0a72ad3fcbf699e2c5ce64bc9195ee3363aebf64'
step_id: 'S75'
related:
  - '[[2026-08-10-aeat-export-fragment-generator-authority-plan]]'
---

# Add the official DP30302 auxiliary activity discriminator to the typed Modelo 303 simplified-regime activity identity endpoint so the annual Orden resolves uniquely, because IAE epígrafe 722 resolves to two Orden activities whose cuota mínima differs by a factor of ten and whose ingreso a cuenta differs 5 per cent against 1 per cent, and 691.9 likewise resolves to two. Prove the identity keys the Orden uniquely for every activity in every pinned Orden year, and refuse an ambiguous resolution rather than selecting a first match. This row must land before any declaration fan-out is authored, or the fan-out bakes in a mis-keying that produces valid output with no refusal in either the under- or over-declaring direction

## Scope

- `src/cadrumo/core/`
- `src/cadrumo/domain/calculations/registry/`
- `src/cadrumo/application/filing/`

## Description

- Confirm the landed discriminator implementation and collision-pair mappings.
- Derive every pinned Orden source from the canonical manifest and census the
  complete `(iae_epigrafe, auxiliary_activity_indicator)` key set.
- Mutate the real 691.9 and 722 payloads to prove missing and duplicate
  discriminators refuse.
- Carry both live collision pairs through the canonical typed projection refs.

## Outcome

Commit `44fd0c839e09bffd9238e77ea6169b95007b3698` supplies the missing durable
proof without changing production or registry data. The all-year census,
four ambiguity mutations, and typed consumer discrimination pass. The two
focused modules report 44 passing tests; Ruff, formatting, and diff checks are
clean.

## Notes

No compatibility identity, fallback selection, or second activity table was
introduced.
