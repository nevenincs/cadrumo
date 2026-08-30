---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-30'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:5f2c3b3123cc6c1ebea90f730007668f15d5cb83b1b1c086a7761522995d3033'
step_id: 'S99'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Retire the three largest domain facades: iva at 179 names across 26 modules, filing at 43 and iva_compensation at 36

## Scope

- `src/cadrumo/domain/`

## Changes

- `M` `src/cadrumo/domain/filing/__init__.py`
- `M` `src/cadrumo/domain/iva/__init__.py`
- `M` `src/cadrumo/domain/iva_compensation/__init__.py`
- `M` `src/cadrumo/domain/iva_compensation/reconciliation.py`
- `M` `src/cadrumo/domain/iva/schema.py`
- `verify:` `pytest src/cadrumo/domain/{filing,iva,iva_compensation} -n 0 -m ""` -> `pass` (928)
- `verify:` `pytest src/cadrumo/application/{aggregation,invoices} src/cadrumo/domain/invoices -n 0 -m ""` -> `fail` (1520 pass, 1 fail)

## Notes

The single consumer failure is the peer registry refactor already identified:
26 registry modules and 20 registry TOMLs are modified in the working tree and
registry validation is all-or-nothing.

Thirteen Protocol property stubs and one validator gained docstrings rather than
a suppression -- publicising a module exposes it to the docstring rules, and a
protocol's members are its contract.
