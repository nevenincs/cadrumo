---
tags:
  - '#exec'
  - '#advisory-grounding'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:493e3bd27b3a94d4c9ecf67558c841b5c44a60dd70936d331da3f41d5a29b218'
step_id: 'S09'
related:
  - "[[2026-08-10-advisory-grounding-plan]]"
---

# Ground the two P03.S06 escalated findings this campaign can adjudicate now. The three LIRPF DT 12a.4 sites in the calculate-input module (_dt12_window_decision's two diagnostics, _dt12_parcial_guidance_advisory) declare asserted_legal_refs against ley-35-2006:dt-12, which resolves cleanly with no gate, same as the sibling _dt12_advisory.py sites already cite it. The recargo-rate-mismatch diagnostic in the modelo-bindings module declares asserted_legal_refs against ley-37-1992:art-161, the recargo de equivalencia provision this project already has a standing rule about. No casilla is in reach for either population, so asserted_legal_refs is the fit, matching the P03.S05 population shape

## Scope

- `src/cadrumo/application/modelo/_calculate_input.py`
- `src/cadrumo/application/aggregation/_modelo_bindings.py`

## Description

- Confirmed `ley-35-2006:dt-12` and `ley-37-1992:art-161` both resolve cleanly in the bundled legal catalogue before touching any site (grep against every `[legal."..."]` block).
- Declared `asserted_legal_refs=("ley-35-2006:dt-12",)` on all three DT 12ª sites: both `CalculationSourceDiagnostic` constructions inside `_dt12_window_decision` (the unverified-window and closed-window branches) and the one inside `_dt12_parcial_guidance_advisory`. No casilla is addressable at any of the three — the diagnostics describe a transitional time-window rule, not the reducción casilla's own value — so the declaration is literal rather than casilla-derived, matching the P03.S05 population shape.
- Declared `asserted_legal_refs=("ley-37-1992:art-161",)` on the recargo-rate-mismatch diagnostic in the modelo-bindings module; the comparison is per invoice, not per casilla, so no registry object is in reach there either.
- Added a grounding assertion per site to the existing live-path test (`test_dt12_window_gate.py`, three tests) and the existing unit test (`test_recargo_rate_advisory.py`, one test), rather than writing new test files, since real coverage of the diagnostics already existed and only needed the new field asserted.

## Outcome

Both P03.S06 escalated findings this campaign could adjudicate without a corpus-vintage dependency are grounded. 13 tests green across both touched test files, ruff/format/ty clean on all four touched files (two production, two test).

The recargo grounding is the smaller of the two by line count but not by weight: LIVA art. 161 is the recargo de equivalencia provision this project has a standing rule about (every IVA total must enumerate the recargo tiers), so a diagnostic that names it without a machine-routable citation was the same "prose only" gap the rest of this campaign closed elsewhere.

## Notes

No incidents. A first attempt to add this row via the plan CLI wrote a corrupted row (a bare semicolon inside the free-text action collided with the row grammar's own `action; \`scope\`` delimiter, and the write-verification check caught the round-trip mismatch but the bad write had already landed on disk). Retired the corrupted `S08` id via `vault plan step remove` and re-added the row with the semicolon rephrased as a period, landing as `S09` — no hand-edit of plan structure at any point, both the bad write and its correction went through owning CLI verbs.
