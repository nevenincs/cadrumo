---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:2e0b53a90c448a968b11a5d1d718eb6db5fbdc488db5ed058ea1fe5c4ed3c101'
step_id: 'S07'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

# classify manual casillas without inferring substitutability from labels or numeric identifiers

## Scope

- `src/cadrumo/application/registry/source_connectivity.py`

## Description

- Classify manual destinations as required or optional from typed registry declarations.
- Leave every non-manual destination unclassified on the manual requirement axis.
- Export the closed manual requirement type through the registry facade.

## Outcome

Every manual destination now carries an explicit required/optional classification derived solely from `InputKind.MANUAL` and the authored `required` flag. No label, number, or lexical inference participates.

## Notes

Ruff passed. A real Modelo 100 2024 snapshot proved that the manual classification is present exactly for typed manual casillas and matches each declaration's required flag.
