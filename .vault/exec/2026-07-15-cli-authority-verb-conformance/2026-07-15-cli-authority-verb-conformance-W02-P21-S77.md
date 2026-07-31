---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-17'
modified: '2026-07-17'
body_hash: 'sha256:863362e8fea20db12020ef3eaebca432a8d6873201762dd59d79d510374cd9e9'
step_id: 'S77'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Prove mnemonic verification and recovery never serialize secret material

## Scope

- `src/cadrumo/adapters/persistence/storage/master_key/tests/test_recovery.py`

## Description

- Add tests for the `atomically_install_verified_recovery` primitive: it installs when verify passes, preserves a prior file when verify raises, and writes nothing on an empty store when verify raises.
- Prove the persisted envelope never contains the plaintext mnemonic words or the master-key hex.
- Prove the verify and recover result records serialize without any secret material, and that a failed recover error envelope omits the mnemonic.
- Prove the recovery fingerprint carries no secret and is deterministic.

## Outcome

Mnemonic verification and recovery never serialize secret material: the on-disk envelope, both outcome records, and the error envelope are all free of the plaintext mnemonic and master key. `uv run --no-sync pytest src/cadrumo/adapters/persistence/storage/master_key/tests/test_recovery.py -q` reports 26 passed.

## Notes

Real file-backed providers are used throughout; the mnemonic is captured via a confirmation callback purely to assert its absence from serialized outputs.
