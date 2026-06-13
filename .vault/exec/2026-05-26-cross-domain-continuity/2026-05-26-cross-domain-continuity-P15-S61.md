---
tags:
  - "#exec"
  - "#cross-domain-continuity"
date: 2026-05-27
modified: '2026-05-27'
step_id: S61
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# cross-domain-continuity P15.S61

## Outcome

Created `src/aeat/entrypoints/cli/test_modelo_casilla_normalisation.py`
with 3 real-adapter tests (no mocks, `isolated_runtime_profile`, real KEK/DEK).

- `test_bare_numeric_resolves_to_canonical_casilla_id`: bare `"69"` normalises
  to `"iva.resultado"` on Modelo 303; proven by the engine error naming the
  resolved id rather than the raw token.
- `test_bare_numeric_unknown_casilla_surfaces_helpful_message`: `"99999"` raises
  `BadParameter` naming the token; no traceback.
- `test_qualified_casilla_key_passes_through_normaliser_unchanged`: qualified
  `"iva.resultado"` produces an engine error naming the canonical id rather
  than an unknown-casilla diagnostic, proving the normaliser did not corrupt it.

All 3 tests pass. Pattern uses `isolated_runtime_profile` + direct
`UserProfileLifecycleRepository.save` to avoid conflict with a live session.

## Commit

`d39dc4328` — W03.P15.S61: regression tests for bare-numeric --casilla normalisation
