---
tags:
  - '#exec'
  - '#casilla-schema'
date: '2026-08-11'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:4453af0d9a91660b8d4cbd5e013ac2c193670e2508b9ef7f524b3be26ae2f04c'
step_id: 'S03'
related:
  - "[[2026-08-10-casilla-schema-plan]]"
---
# Widen the XML dictionary casilla identifier parser

## Scope

- `src/cadrumo/domain/calculations/registry/_export_parse.py`

## Description

- Preserve numeric dictionary identities as the default convention.
- Admit one uppercase ASCII letter only for official dictionary sources applying from 2024 onward.
- Reject notes, starred metadata, lowercase, non-ASCII, multi-letter, and mixed identities.
- Exercise the 2024 and 2025 conventions against the bundled Modelo 100 dictionaries.
- Update the independent conformance measurement to expose the ten official letter identities.

## Outcome

The parser preserves numeric behavior before 2024 and surfaces the official 2024 and 2025 `A`, `C`, `D`, `E`, `F`, `G`, `H`, `I`, `J`, and `M` identities. The focused implementation lane passed 24 tests; the independent review lane passed 43 tests. Ruff, Ruff format, BasedPyright, scoped diff checking, and `aeat app registry verify` passed.

## Notes

No compatibility alias, broad alphanumeric grammar, or source-byte mutation was introduced. The surfaced letter identities remain visible as conformance extras rather than being silently discarded. No compatibility reader, normalization rule, fake source, mock, stub, patch, skip, or xfail was introduced.

This step was executed twice in parallel on diverged history. Both executions reached the same digits-or-one-uppercase-letter grammar and the same refusal set, and both proved it against the real bundled Modelo 100 2024 and 2025 dictionary rows; the second additionally framed the grammar as an outright replacement of the digits-only parser rather than a widening. Reconciling the two, this lane's implementation is canonical and no behaviour from the parallel execution was lost.
