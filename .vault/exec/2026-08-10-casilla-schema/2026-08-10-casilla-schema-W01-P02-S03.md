---
tags:
  - '#exec'
  - '#casilla-schema'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:b097c602f47491f342f106e98e3ab94cef64d5ce01104d0284f30a629c6ac673'
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

No compatibility alias, broad alphanumeric grammar, or source-byte mutation was introduced. The surfaced letter identities remain visible as conformance extras rather than being silently discarded.
