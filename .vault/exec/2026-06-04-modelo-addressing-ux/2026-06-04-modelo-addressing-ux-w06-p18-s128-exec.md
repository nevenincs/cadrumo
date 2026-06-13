---
tags:
  - '#exec'
  - '#modelo-addressing-ux'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S128'
related:
  - '[[2026-06-04-modelo-addressing-ux-plan]]'
---

# W06.P18.S128 exact CLI business-logic leakage audit

Scope:
- `rg CLI business-logic leakage audit`

## Description

- Run exact production CLI search for domain-internal imports, application-private imports, registry selection, workflow persistence, calculation calls, filing calls, export calls, reconciliation calls, legal article text, casilla value arithmetic, and current/filed pointer handling.
- Exclude CLI tests from the production command-module audit.

## Outcome

The audit found material business-logic leakage in production CLI modules. Immediate modelo-addressing findings:

- `_modelo.py` imports application lifecycle functions directly and also imports application-private selectors.
- `_modelo.py` imports domain registry objects, domain row models, domain calculation revision state, work units, filing records, verification reports, and tax-rule computation functions.
- `_modelo.py` resolves registry revision selection inside `work_create`.
- `_modelo.py` computes special tax inputs inside `work_calculate`, including Art. 7.h, Art. 81, DT 12 LIRPF, Ley 44/2015 Art. 14, and LISIVA Art. 9/79/90 flows.
- `_modelo.py` fetches workflow state inside verify, file, export, modality, applicability, and preview command bodies.
- `_modelo.py` computes projection and comparison values directly from `casilla_values`.
- `_ledger.py`, `_config/__init__.py`, `_config/_google.py`, `_app_live.py`, and `registry.py` also show broader CLI boundary debt, but `_modelo.py` is the required mitigation target for this ADR.

## Notes

- No code was changed by this audit step.
