---
step_id: "S17"
tags:
  - "#exec"
  - "#trabajador-del-mar"
date: "2026-05-31"
modified: '2026-05-31'
related:
  - "[[2026-05-31-trabajador-del-mar-plan]]"
  - "[[2026-05-31-trabajador-del-mar-adr]]"
---

# trabajador-del-mar W02.P05.S17 step record

## Step

Wire trabajador_del_mar calculation output through the application calculations service preserving CasillaObservation list alongside flat casilla_values.

## Files Touched

- `src/aeat/application/calculations/_maritime_exemption_service.py` — resolve_maritime_exemption function and MaritimeExemptionResult model. Accepts MaritimeWorkerFacts + income inputs, routes to domain calculation functions, returns typed observation tuple alongside derived casilla_values mapping.

## Commit

`fe9a6d753` — feat(application/calculations): W02.P05 maritime exemption service + integration tests

## BOE Citations

Per calculation pathway — see S12 (Art. 7.p)) and S13 (REBECA).

## Outcome

resolve_maritime_exemption correctly routes to art_7p_eligible / rebeca_eligible pathways. DA 41 inactive guard fires before any calculation. RETMAR gate checked independently. MaritimeExemptionResult carries typed observations as canonical contract and flat casilla_values as derived human-readable view per aeat-calculation-grounding.
