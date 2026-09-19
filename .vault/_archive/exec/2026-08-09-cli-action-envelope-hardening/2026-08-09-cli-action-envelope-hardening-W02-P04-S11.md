---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:10341e77e3abc5aeb8e8a560abcad4a882692befd505f97e59558b42c0490682'
step_id: 'S11'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---

# Project resolved typed actions through notices while keeping localized text derived

## Scope

- `src/cadrumo/core/json_contract.py`

## Description

- Add strict frozen wire DTOs for evaluated condition evidence, resolved action
  identity, resolved or missing argument bindings, conditionality, and explicit
  no-recovery outcomes.
- Make `Notice.action` the exclusive executable-action transport; remove the
  `Notice.suggestion` compatibility field and preserve localized `message` as
  presentation only.
- Reject raw executable `aeat` prose, presentation-bearing evidence keys, and
  every reserved action-guidance key from non-action notice context.
- Canonicalize evidence, binding, and missing-name order; deeply freeze factual
  mappings while serializing their deterministic wire form.
- Address the review follow-up with direct production-constructor adversarial
  tests and action-bearing success-envelope JSON round trips.

## Outcome

The core envelope now carries a resolved action only as typed identity, target
command key, evidence, bindings, conditionality, or an explicit terminal,
safety, or operator-decision outcome. It imports no application guard,
catalogue, Click, or command-resolution policy.

The review remediation proves invalid wire states fail at the core boundary:
identity and evidence joins, source/value/type equality, missing-input shape,
outcome XOR, conditionality, presentation leakage, reserved context keys,
canonical order, and deep immutability. Two full JSON-text envelope round trips
prove both resolved and no-recovery projections survive serialization.

## Verification

`uv run --no-sync pytest -n0 src/cadrumo/core/tests/test_json_envelope_roundtrip.py -q`

`22 passed in 0.82s`

`uv run --no-sync ruff check src/cadrumo/core/json_contract.py src/cadrumo/core/tests/test_json_envelope_roundtrip.py`

`All checks passed!`

`uv run --no-sync basedpyright src/cadrumo/core/json_contract.py src/cadrumo/core/tests/test_json_envelope_roundtrip.py`

`0 errors, 0 warnings, 0 notes`

## Notes

The cutover debt is explicit and LOW for this contract-only Step: 51 existing
producer `Notice(..., suggestion=...)` sites still require migration and are
not evidence that the new core projection has been adopted. Their exclusive
planned owners are the boundary transport work in S12 and S16-S18, workflow and
modelo slices S21-S26, registry slices S28 and S50-S57, and the remaining
producer and renderer slices S31-S41 and S58-S61. No producer was migrated or
claimed closed here; the fixed-point join and runtime recovery proof remain
owned by S42-S48.
