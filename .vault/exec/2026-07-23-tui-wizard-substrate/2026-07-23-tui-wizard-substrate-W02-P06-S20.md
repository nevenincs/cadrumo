---
tags:
  - '#exec'
  - '#tui-wizard-substrate'
date: '2026-07-24'
modified: '2026-07-24'
step_id: 'S20'
related:
  - "[[2026-07-23-tui-wizard-substrate-plan]]"
---

# Prove copy resolution against real schema and locale sources including the four-locale parity of the new namespaces

## Scope

- `src/cadrumo/application/flows/tests/test_copy_assembly.py`

## Description

- Prove copy resolution against real schema and locale sources, including four-locale parity of the new help, format-hint, and failure-mode namespaces.
- De-tautologize the assertions and decouple the unregistered-resolver refusal case from any real copy kind.
- Landed in `10506c8833` (test_copy_assembly.py), de-tautologized in `2b2c93bf90`, and decoupled by NIT-15 in `f9f5292405`.

## Outcome

Copy assembly is pinned against live schema and locale catalogues with genuine assertions; the unresolvable-reference refusal is proven without depending on any concrete copy kind.

## Notes

None.
