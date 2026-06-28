---
step_id: "S18"
tags:
  - "#exec"
  - "#trabajador-del-mar"
date: "2026-05-31"
modified: '2026-05-31'
related:
  - "[[2026-05-31-trabajador-del-mar-plan]]"
  - "[[2026-05-31-trabajador-del-mar-adr]]"
---

# trabajador-del-mar W02.P05.S18 step record

## Step

Write integration test asserting CLI JSON emit includes legal_refs and source_refs for each maritime exemption CasillaObservation.

## Files Touched

- `src/aeat/application/calculations/test_maritime_exemption_service.py` — 18 integration tests covering: Art. 7.p) legal_refs + source_refs end-to-end (TestResolveMaritimeExemptionArt7p), REBECA legal_refs + source_refs (TestResolveMaritimeExemptionRebeca), DA 41 inactive guard fires before observations (TestResolveMaritimeExemptionDa41Guard), RETMAR completeness gate (TestResolveMaritimeExemptionRetmarGate).

## Commit

`fe9a6d753` — feat(application/calculations): W02.P05 maritime exemption service + integration tests

## BOE Citations

- Ley 35/2006 Art. 7.p) BOE-A-2006-20764 — verified in legal_refs of Art. 7.p) observation
- Ley 19/1994 Arts. 73.2 73.3 75.1 75.3 BOE-A-1994-16100 — verified in legal_refs of REBECA observation
- Ley 47/2015 BOE-A-2015-11346 — RETMAR gate verified in ProfileCompletenessError context

## Outcome

All 18 integration tests pass. legal_refs and source_refs are asserted present in each maritime exemption CasillaObservation. W02 close gate: zero rg hits for "DA 24" and "dietas a bordo" in src/aeat/domain/renta/ and src/aeat/application/calculations/.
