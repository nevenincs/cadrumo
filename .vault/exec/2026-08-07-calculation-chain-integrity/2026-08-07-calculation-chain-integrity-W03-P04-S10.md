---
tags:
  - '#exec'
  - '#calculation-chain-integrity'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:132d17e3680a8a611aaed9978ddf206c6c0fa914d045a69bdc81d07ec65e3025'
step_id: 'S10'
related:
  - "[[2026-08-07-calculation-chain-integrity-plan]]"
---
# `calculation-chain-integrity` exec `W03-P04-S10`: Record the placement ruling against the deferring ADR

## Scope

- `.vault/adr/2026-08-07-calculation-chain-integrity-activity-type-placement-adr.md`

## Summary

The ruling is recorded as its own ADR rather than as an amendment, because the
accepted silent-zero-base-aggregation record defers on this axis rather than
deciding it, and a deferral is not a decision to rewrite in place.

That accepted ADR is cited as grounding and its deferral is quoted in the
problem statement: Modelo 130 casilla 08 "needs an agrarian-vs-directa
classification axis the transaction model lacks". The new record answers exactly
that, and names casilla 08 alongside the retención narrowing as the two
consumers the one capability unblocks.

Grounding references were added after the schema check refused the record for
carrying none: the multi-activity profile reference, which measures the AEAT
per-slot row as *(descripción, sección, grupo/epígrafe, tipo de actividad)*, the
proposed ADR that acts on it, and the deferring ADR itself. The schema check is
clean; the remaining tree warnings are pre-existing and belong to peer documents.
