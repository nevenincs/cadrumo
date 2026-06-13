---
tags:
  - "#exec"
  - "#cross-domain-continuity"
date: 2026-05-27
modified: '2026-05-27'
step_id: S77
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# cross-domain-continuity P20.S77 — verification boundary docstring

## Outcome

Added a "Verification boundary" section to the module docstring in
`src/aeat/application/modelo/__init__.py` documenting the four-layer gate
that `verify_modelo_revision` enforces before granting `VERIFICADO_COMPLETO`:

1. State machine gate (`BORRADOR` state required)
2. Per-casilla required-input gate (Layer 1, `CasillaDefinition.required`)
3. Cross-casilla predicate gate (Layer 2, `VerificationPredicateDefinition`)
4. Provenance re-validation (`_assert_revision_content_integrity`, `StoredCalculationDriftError`)

Import sort and `__all__` sort were also fixed to satisfy ruff (`I001`, `RUF022`).

## Files changed

- `src/aeat/application/modelo/__init__.py` (docstring + import/`__all__` sort)
