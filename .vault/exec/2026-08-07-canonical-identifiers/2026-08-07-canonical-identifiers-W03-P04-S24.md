---
tags:
  - '#exec'
  - '#canonical-identifiers'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:bbfceb38447d9eb22f1d24caf7fabdb42b86f9dfb3dea30fbf8559b486313400'
step_id: 'S24'
related:
  - "[[2026-08-07-canonical-identifiers-plan]]"
---
# drop the unconsumed resolver with the dormant namespace enum

## Scope

- `src/cadrumo/core/identity/_namespace.py`
- `src/cadrumo/core/identity/__init__.py`

## Description

- Consume the S64 production-consumer adjudication.
- Drop `resolve_identifier_namespace` without implementation because no production value has an unknown namespace at its point of use.
- Delete the dormant `IdentifierNamespace` catalogue and its facade export while retaining direct canonical aliases.

## Outcome

S24 closed as dropped-without-resolver-implementation under S64. The production census found no consumer that needed runtime namespace resolution: field types already carry the namespace fact. Implementing a resolver would therefore manufacture a parallel authority with no consumer.

The same landed change deleted the dormant `IdentifierNamespace` enum and removed its facade export. Direct canonical identity aliases remain the sole production authority. The focused identity suite passed with 18 tests, Ruff, formatting, Ty, facade alias imports, and a zero-match census for the retired names.

## Notes

This record supplies the missing per-step traceability for the already-landed S64 deletion commit. It does not claim that a resolver was implemented.
