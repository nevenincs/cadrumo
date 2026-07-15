---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-11'
modified: '2026-07-11'
step_id: 'S365'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# M100 negative base-liquidable-general carry legal grounding

## Scope

- `src/aeat/_data/registry/aeat/modelos/100/revisions/2025/{bindings,casillas,formulas,constructs,verification}/`
- `src/aeat/application/modelo/tests/`
- `src/aeat/domain/calculations/registry/tests/`

## Description

- Grounded the 1391-to-1388-to-0501 base-liquidable-general route in the bundled LIRPF Art. 50.3 authority, including its four-year compensation rule.
- Corrected 2024 and 2025 bindings, Anexo C casillas, cap/roll-forward formulas, predicates, and constructs so the base-liquidable route names Art. 50 rather than Art. 48.
- Registered the computed Art. 50 chain `1391 -> 1388 -> 1389 -> 0501 -> 0500`; 1389 no longer disappears from the calculation after removal from the base-imponible formula.
- Retained Art. 48 only for the distinct base-imponible 0432-to-0433 route and extended live carry and registry-chain regressions with authority-backed Art. 50-not-Art. 48 assertions.

## Outcome

- The reported manual-transcription defect is not present: prior-year 1391 enters current-year 1388 without manual 0501 input.
- The base-liquidable carry now has the correct principal Art. 50 grounding, while the base-imponible mechanism retains its distinct Art. 48 authority.
- A real encrypted-store regression proves a 2,000 amount on 1389 computes 0501 at 2,000, reduces 0500 by 2,000, and leaves 0435 unchanged.
- The final application-calculations and encrypted live run passed 13 tests in 16.75 seconds; catalogue validation passed 18 tests in 14.18 seconds; owned Ruff and whitespace checks passed.

## Notes

- The initial two-test evidence exposed both wrong legal grounding and an incomplete compensation path; the final record includes the authority correction, the computed 1389-to-0501 mechanism, and a reconciled compensation oracle.
