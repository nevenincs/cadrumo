---
tags:
  - '#exec'
  - '#legal-grounding-centralization'
date: '2026-06-14'
modified: '2026-06-15'
step_id: 'S05'
related:
  - "[[2026-06-14-legal-grounding-centralization-plan]]"
---




# F3: resolve M303/M390 compensación casilla ids through the registry snapshot casilla definitions instead of inline numeric literals

## Scope

- `src/aeat/application/calculations/_iva_compensation_history.py`

## Description

- Add `_casilla_id_to_number(modelo)` (lru-cached): build a registry casilla
  id→official-number map from the loaded registry tree, so the official AEAT box
  number is registry-owned data, not an inline routing literal.
- Add `_registry_casilla_value(values, modelo, semantic_id)`: resolve a filed-observation
  value under both the registry-resolved box number and the semantic casilla id.
- Refactor the M303 (`iva_compensation_state_from_filed_observation`) and M390
  (`iva_compensation_annual_summary_from_filed_observation`) lookups to reference only the
  stable semantic casilla id; the seven inline numeric literals (69/87/110/78/71 and
  97/662) are now resolved from the registry. The `cross_check` `mismatched_casillas`
  output labels keep the box numbers — they are operator-facing identifiers, not routing.

## Outcome

The M303/M390 compensación casilla routing now resolves through the registry casilla
definitions (`aeat-schema-central-config`), closing finding F3. Verified the resolver maps
every semantic id to its original number exactly (iva.resultado→69,
compensacion-pendiente-anteriores→110, 71→71, M390 97/662); behaviour-preserving — 19
compensation-history tests plus the full application/calculations (335) and
application/modelo (488) suites pass; ruff clean.

## Notes

The registry id→number map merges revisions (later wins on the rare collision); the
compensación box numbers are stable across M303/M390 revisions, so this is safe for the
projection/cross-check path (not the law-determined calculation path). Casilla 71 has no
semantic id in the registry (its id IS "71"), so it is referenced by that canonical id —
not a duplicated routing literal. Running the broader suites surfaced — and this campaign
absorbed — F4 fallout in three M303 calc test helpers (committed separately); the F3
refactor itself is behaviour-preserving.
