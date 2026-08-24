---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:3ff9f13b2fbea5ee67a0b360e89d795606edf7b3b6dbc5d009bd62e72154bb9c'
step_id: 'S127'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---
# Migrate outbound-storage integrity and mirror-manifest mismatch, malformed-schema, and corruption failures to typed safety or validation outcomes

## Scope

- `src/cadrumo/adapters/outbound/storage/_integrity.py`
- `src/cadrumo/adapters/outbound/storage/_mirror_manifest.py`
- `src/cadrumo/adapters/outbound/storage/tests`

## Description

- Project content-hash, digest-shape, and byte-length failures as typed safety refusals.
- Project malformed and unsupported mirror manifests as typed safety refusals.
- Project remote namespace mismatch as a typed operator-decision refusal.
- Reuse the canonical no-action precondition helper without redeclaring verdict or evidence construction.
- Assert the exact condition, evidence facts and provenance, action absence, conditionality, and outcome for every refusal family.

## Outcome

All six owned integrity and mirror-manifest refusal families now carry stable machine-readable precondition evidence. Corruption and malformed-schema cases resolve to `SAFETY`; namespace mismatch resolves to `OPERATOR_DECISION`. Every refusal has no action and `NOT_APPLICABLE` conditionality.

Focused storage tests pass 30 cases and scoped Ruff checks are clean. Independent closure review passed after verifying the implementation uses the shared canonical helper and the tests discriminate every owned family.

## Notes

- VaultSpec RAG discovery and exact source scanning found no local verdict or evidence constructor in this scope.
