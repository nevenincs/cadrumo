---
tags:
  - '#exec'
  - '#deadline-window-revision-authority'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:515cadde0ddbed2f74c242a65866406d88eee5262cedf372e19163a50eae8517'
step_id: 'S02'
related:
  - "[[2026-08-24-deadline-window-revision-authority-plan]]"
---

# Add optional typed deadline qualifiers reusing ResultDisposition and official M210 tipo-renta code authority without a lossy TipoRentaIrnr projection

## Scope

- `src/cadrumo/domain/calculations/registry/_schema.py`

## Description

- Add an optional `resultado_scope` typed by the public canonical `ResultDisposition`.
- Add an optional multi-code `tipo_renta_scope` that preserves official two-digit codes.
- Validate tipo-renta scope membership through the public canonical official-code projection already parity-gated against registry declarations.
- Reject empty, duplicate, malformed, and unknown tipo-renta scopes without introducing a conceptual projection.
- Add focused schema regressions for defaults, hydration, and refusal cases.

## Outcome

`DeadlineWindowDefinition` now expresses the two accepted qualified-plazo axes while
leaving every existing unqualified row unchanged. Official tipo-renta identity remains
the byte-exact code rather than the many-to-one rate concept.

## Notes

The initial parallel pytest attempt suffered an xdist worker crash before test
execution. Serial focused runs passed: five qualifier tests and four existing
deadline-window source-tier tests. Ruff passed on both modified Python files.
