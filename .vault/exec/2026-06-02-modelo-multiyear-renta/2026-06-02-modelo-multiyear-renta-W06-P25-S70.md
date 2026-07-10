---
tags:
  - '#exec'
  - '#modelo-multiyear-renta'
date: '2026-07-06'
modified: '2026-07-06'
step_id: 'S70'
related:
  - "[[2026-06-02-modelo-multiyear-renta-plan]]"
---

# assert the Modelo 721 registry keeps threshold parameters and filing/extractor/verification/deadline links without a calculation application-link surface

## Scope

- `src/aeat/_data/registry/aeat/modelos/721/`

## Description

- Verify the committed Modelo 721 registry application links expose portal, filing, extractor, verification, and deadline surfaces.
- Assert the registry does not expose `surface = "calculation"` or construct membership for `modelo-721-calculation`.
- Preserve the threshold parameters required by the two-year continuity test.

## Outcome

- Satisfied by the Modelo 721 registry and the dedicated registry regression test.
- Modelo 721 remains an informativa threshold-continuity surface, not a numeric calculation surface.

## Notes

- This closes the stale calculation-link row only.
- It does not implement the remaining `S89` row-set prior-year baseline binding question.
