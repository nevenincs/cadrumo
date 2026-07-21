---
tags:
  - '#exec'
  - '#calculation-source-connectivity'
date: '2026-07-04'
modified: '2026-07-08'
step_id: 'S55'
related:
  - "[[2026-05-20-calculation-source-connectivity-plan]]"
---

# Re-run registry source inventory after each implementation wave

## Scope

- `src/aeat/_data/registry/aeat/modelos`

## Description

- Re-run the registry source inventory as the campaign closeout governance pass: the source-enrollment gate (`test_source_enrollment.py` + `test_source_mesh_missing_sources.py`) and the domain `source_inventory` report.

## Outcome

Stable-window run: 9/9 green. Every binding `source` kind declared across the committed registry is enrolled, explicitly deferred, or manual — no dormant/unenrolled surface. Modelo 145 (peer-landing) declares no calculation binding sources (only a `workbook_source` parity ref, no `bindings/` dir), so it adds no source kinds. Recorded in the campaign closeout audit.

## Notes

A concurrent re-run flipped to 8 failed / 1 passed; full-traceback isolation proved every failure is `RegistryLoadError: registry directory changed during cache fingerprinting` — the transient loader-cache race from the concurrent modelo-145 export write, NOT a calc-source gap (a real one would be a naming assertion, not a load error). A MANDATORY settle-window re-confirm of a real 9/9 green on the settled registry is tracked in the closeout audit's recommendations.
