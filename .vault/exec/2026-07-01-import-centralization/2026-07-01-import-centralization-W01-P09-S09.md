---
tags:
  - '#exec'
  - '#import-centralization'
date: '2026-07-05'
modified: '2026-07-17'
body_hash: 'sha256:e8734cb34d6f75477960880463cb55250a4792a75d38cc57f28c653ecd185e9e'
step_id: 'S09'
related:
  - "[[2026-07-01-import-centralization-plan]]"
---

# Promote `BrowserAdapterTypeError`, `GroiSedeDriver`, `NifIvaCheckSedeDriver`, `filed_declaracion_observation_object_key`, `iva_compensation_wallet_observation_object_key` to `aeat.adapters.outbound.aeat.sede.__all__` with eager re-exports so the 5 existing cross-package consumer site(s) can import from the facade

## Scope

- `src/aeat/adapters/outbound/aeat/sede/__init__.py`
## Description

- Reconcile $display as an individual exec record for a W01 facade-promotion row already checked in the plan.
- Preserve the row intent: Promote `BrowserAdapterTypeError`, `GroiSedeDriver`, `NifIvaCheckSedeDriver`, `filed_declaracion_observation_object_key`, `iva_compensation_wallet_observation_object_key` to `aeat.adapters.outbound.aeat.sede.__all__` with eager re-exports so the 5 existing cross-package consumer site(s) can import from the facade.
- Tie this row to the AEAT Sede promotion recorded by the existing `W01.P03.S02` exec record and landed in `9d6af8015`.
- Record no new implementation work; this document splits already-landed umbrella evidence into the required one-record-per-step shape.

## Outcome

The checked row now has its own exec record. The matching umbrella evidence for $anchor recorded direct facade-resolution probes, ruff checks, and clean `pytest --collect-only -q src/aeat` from the umbrella record. The W01 scaffold pass removed $(W01.P09.S09.Split('.')[-1]) from xec_missing_ids at plan status time.

## Notes

Evidence-only reconciliation. The codebase has continued to evolve after the original W01 landing, so this record intentionally cites the historical landed evidence and does not claim a fresh source edit.
