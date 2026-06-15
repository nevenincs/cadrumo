---
tags:
  - '#exec'
  - '#service-capabilities'
date: '2026-06-15'
modified: '2026-06-15'
step_id: 'S04'
related:
  - "[[2026-06-15-service-capabilities-plan]]"
---




# Rewire cloud_evidence_read_permitted, the vision path, and google export through resolve_capability with typed refusals

## Scope

- `src/aeat/application/ledger/_evidence_input.py`

## Description

- Rewire `cloud_evidence_read_permitted` through the resolver; gate the on-host vision read on llm_vision; gate google calc-sheets export on google_export. Each opt-out is a typed refusal with the enable command.

## Outcome

All three service gates route through the one resolver; existing evidence/vision/google tests green (default-on preserved).

## Notes

Profile linkage complete for the three operator-named services (cloud, llm vision, google).

