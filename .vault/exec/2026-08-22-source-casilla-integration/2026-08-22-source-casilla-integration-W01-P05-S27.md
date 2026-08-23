---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:a4de5f43da2b5f3d7e8792f51af4f4abf5bf2f979c761096f85a80cd61b27988'
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
