---
step_id: S66
tags:
  - '#exec'
  - '#identity-primitives'
date: '2026-05-30'
modified: '2026-05-30'
related:
  - '[[2026-05-30-identity-primitives-plan]]'
  - '[[2026-05-30-identity-primitives-adr]]'
  - '[[2026-05-30-identity-primitives-reference]]'
---

# identity-primitives W05.P19.S66 — private-name _ids import detector

## Scope

Land the second ADR Rule 9 detector: assert no adapter,
application, or entrypoint module imports a leading-underscore
name from any `_ids.py` module. The public typed-alias names
are the cross-layer contract; reaching for the underlying
regex constants, length constants, or private re-aliases is a
type-system escape under the calculation-grounding rule.

## Outcome

Extended `src/aeat/diagnostics/_identity_placement.py` with
`find_private_id_imports`. The detector walks every
`aeat.adapters.*`, `aeat.application.*`, and
`aeat.entrypoints.*` module, parses `from <pkg>._ids import …`
statements, and flags any imported name whose first character
is an underscore.

Added `test_no_private_id_imports` to
`src/aeat/diagnostics/test_identity_primitive_placement.py`.

## Verification

`uv run --no-sync pytest
src/aeat/diagnostics/test_identity_primitive_placement.py`
runs both detectors (2 passed, 2.83s). The post-W03 CLI
private-regex cleanup (W03.P12.S53 deleted the `_CASILLA_RE` /
`_REF_RE` import in `entrypoints/cli/_modelo.py`) leaves no
consumer-layer private-name `_ids` imports for the detector
to surface.
