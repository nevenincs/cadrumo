---
tags:
  - '#exec'
  - '#casilla-schema'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:ae17ded8fbbdcfca30e3b2f5c651c3cf7f7836ecd2cbc97659fa90a59a5c67a3'
step_id: 'S06'
related:
  - "[[2026-08-10-casilla-schema-plan]]"
---
# Remove phantom constant-value source kind

## Scope

- `src/cadrumo/entrypoints/cli/_modelo_discovery_cli.py`
- `src/cadrumo/application/state_projection.py`
- `src/cadrumo/application/modelo/_required_binding_gate.py`
- Adjacent explanatory surfaces and direct behavior tests.

## Description

- Delete every production reference to the retired `constant_value` pseudo-source.
- Let the canonical `BindingSourceKind` enum and compiled registry remain the sole source-kind authority.
- Preserve `bindings list --missing` through profile-resolved binding ids and registry-derived `operator_input_required`.
- Delete the echo-only filter test and retain real strict-subset and no-profile behavior proofs.

## Outcome

Production contains zero exact `constant_value` references. The canonical enum and loaded registry both reject the retired token, while real missing-binding behavior remains intact. Sixteen focused tests passed, the registry verifier remained green at 73 modelos and 94 revisions, Ruff and focused BasedPyright passed, formatting and scoped diff checks are clean, and formal independent review found no actionable issues.

## Notes

The exact console command reached the current profile-session guard and returned the canonical typed login action, so the live console path could not exercise binding listing without mutating authentication state. Broader unrelated tests remain red on stale action payload assertions and profile fixtures missing newly required jurisdiction or Modelo IVA composition fields; broad legacy CLI typing debt was not claimed green.
