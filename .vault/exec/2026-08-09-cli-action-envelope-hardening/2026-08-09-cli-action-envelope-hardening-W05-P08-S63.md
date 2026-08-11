---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:f50f61fc5fead474b95203aa4d2ca03df57532f8fcfe20ec7b833ebb3996f04c'
step_id: 'S63'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---
# Prove CadrumoError has no retired suggestion parameter or attribute and retain every unmigrated producer or consumer as a loud later-step blast radius without restoring compatibility

## Scope

- `src/cadrumo/core/errors/__init__.py`

## Description

- Ground the base exception contract with semantic, exact, AST, runtime-signature, and inheritance-surface discovery.
- Replace the stale S63 migration action through guarded Vault CLI with the current strict-boundary proof.

## Outcome

- `CadrumoError` exposes only `message`, `context`, and `translated_message`; neither AST nor runtime signature has a `suggestion` parameter or attribute.
- No production `CadrumoError` suggestion constructor or base-attribute consumer remains. Optional-extra packaging consumers are outside S63 and remain loud for their later owner.
- Direct rehoming validation passed with `E_REHOMING_VALIDATED:238`; Ruff, format, and BasedPyright passed.

## Notes

- The real exception-base hygiene lane is red for two external builtin-root producers: `FilingProducerSnapshotError` and `OrdenAnualHtmlParseError`. No compatibility surface was restored and no external source was changed.
- S63 remains open for independent review. The full rehoming lane was not run after this external focused-gate failure.
