---
tags:
  - '#exec'
  - '#profile-registration-password-policy'
date: '2026-08-22'
modified: '2026-08-22'
body_schema: 'body-v1'
body_hash: 'sha256:319e99577c1436350617a1a1d4bd498240c637ded097b86270e15cfade88019f'
step_id: 'S06'
related:
  - "[[2026-08-22-profile-registration-password-policy-plan]]"
---

# Ground code and governing ADRs with vaultspec-rag, confirm exact symbols with rg, reread HEAD, inspect overlapping diffs, then separate recovery-secret encoding across parent and worker and prove unchanged mnemonic, envelope, transport, and derivation roundtrips

## Scope

- `src/cadrumo/adapters/persistence/storage/custody`

## Description

- Introduce an exact strict-UTF-8 recovery-secret codec with no password-policy dependency or normalization.
- Split parent supervision and isolated-worker protocol operations into explicit password and recovery capabilities.
- Remove the conflated material entry points and migrate every custody caller to the capability it owns.
- Prove exact Unicode preservation, malformed transport refusal, negative-space policy separation, and worker-backed roundtrips.

## Outcome

Recovery mnemonics now retain their exact UTF-8 bytes through both supervision boundaries without invoking canonical profile-password assessment. Password operations retain canonical validation. Focused worker and codec tests passed, and the full custody surface remains lint-clean.

## Notes

The first parallel full-custody run encountered a pre-existing xdist worker crash in a path-identity test. The deterministic focused suite passed with xdist disabled; no byte-parity or ADR conflict was found.

Review remediation added a real parent-to-isolated-worker recovery wrap and unwrap using the non-password-shaped `short` candidate, exact AAD, the persisted sentinel fixture, and an exact DEK assertion. The paired password operation refuses the same candidate with canonical `too_few_scalars`; static routing coverage now includes both supervision owners. Ruff check and format-check pass over all owned modules and tests. The focused worker/codec lane passes 28 tests, and the complete serial default custody lane passes 218 tests with 10 expected marker deselections.
