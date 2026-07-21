---
tags:
  - '#exec'
  - '#binding-fold-in-carry-unification'
date: '2026-06-26'
modified: '2026-07-17'
step_id: 'S09'
related:
  - "[[2026-06-26-binding-fold-in-carry-unification-plan]]"
---

# vaultspec-code-reviewer: VERIFICATION GATE 3 - assert the M303 modelo-303-compensacion-pendiente-anteriores carve-out and the relation/previous_filing collision gate still fire EXACTLY ONCE post-dedup, never a double-fire

## Scope

- `src/aeat/domain/calculations/registry/_validate_relation_sources.py`

## Description

- Verification gate 3: assert the M303 iva-wallet carve-out (`modelo-303-compensacion-pendiente-anteriores`) and the relation/previous_filing collision gate still fire EXACTLY ONCE post-dedup, never a double-fire, and that M353 per_grupo_member fan-in is preserved.

## Outcome

- The full committed-registry build validates clean (41 tests), which runs the collision gate exactly once at build and exercises the M303 carve-out and slot-source hygiene; the M303 carry anti-regression and M353 per_grupo_member surfaces passed. The collision-gate module and the carve-out frozenset were not touched by the S05 to S07 dedup (they operate on binding ids and selector shapes, not the requirement records), so they fire exactly as before by construction.

## Notes

- No code change in this gate Step. Confirmed `_validate_relation_sources.py`'s carve-out frozenset and two-gate hygiene are unchanged since before S05; the dedup did not collapse the carve-out into a double-fire.
