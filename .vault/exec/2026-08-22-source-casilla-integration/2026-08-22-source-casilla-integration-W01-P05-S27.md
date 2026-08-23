---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:5fc4f4bf37eae017cdc4f4200fabed258a688dcb22d5c59fe38b7e7b31ba8c44'
step_id: 'S27'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

# reject connected claims without resolver ownership and encrypted revision proof

## Scope

- `dev/source_connectivity/check.py`

## Description

- Accept the canonical live proof authority at the census gate boundary.
- Hydrate connected census rows only through authority-backed strict validation.
- Convert missing or failed resolver, workflow, evidence-digest, and encrypted-revision proof into a typed gate failure.
- Reuse the existing connected-proof contract and live authority instead of creating parallel proof semantics.

## Outcome

Any future `connected` census claim now reaches the existing live proof authority through the monotonic
gate. A claim cannot pass on authored TOML alone: it requires exact canonical resolver ownership, a
supported operator workflow, unchanged executable evidence, and matching primary provenance loaded from
the encrypted calculation revision. The current census contains no premature connected claims and passes.

## Notes

Ruff passed, the live census comparison passed, 47 core connectivity contract tests passed, and 15 real
authority integration tests passed sequentially.
