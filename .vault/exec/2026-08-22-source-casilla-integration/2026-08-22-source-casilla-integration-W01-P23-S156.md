---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:d1e8dd07ddc433dad78ba592e7a942d5ded788a6ee89c8ac3db44f54d831457c'
step_id: 'S156'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---




# replace advisory destination strings with typed registry-resolvable candidate identities and fail on absent or ambiguous destinations

## Scope

- `src/cadrumo/application/registry/source_connectivity.py`

## Description

- Introduce a strict typed identity for semantic-role and binding-source registry destination candidates.
- Separate registry-resolvable candidates from lexical and family-level advisory hints.
- Resolve accepted candidates against validated modelo revisions and refuse absent or revision-ambiguous identities.
- Enroll destination validation in the monotonic census check and prove both failure directions.

## Outcome

The source census now has a verified destination side. Three exact Modelo 100 inventory semantic roles and
four existing row binding-source families resolve against live registry authority and have one census owner.
Invented semantic roles and roles that identify multiple casillas in one revision fail. Amortization, finca,
asset, and Modelo 296 hints remain honestly advisory until official adjudication establishes an exact target.

## Notes

Ruff passed. Four destination-focused tests passed sequentially against the live validated registry. The
whole comparison currently also detects an unrelated concurrent CLI refactor that reduced discovered ingress
surfaces; its frozen digest was deliberately not refreshed from peer work in progress.
