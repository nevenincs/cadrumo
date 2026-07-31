---
tags:
  - '#exec'
  - '#cli-authority-quality-backlog'
date: '2026-07-17'
modified: '2026-07-19'
body_hash: 'sha256:9eac0c56970b0e6e6af8a0024be202a0d4ae9cf61a151ad80ca2bf1b292e6fde'
step_id: 'S05'
related:
  - "[[2026-07-17-cli-authority-quality-backlog-plan]]"
---

# Prove the recurrence gate rejects a new reducible one-shot body and accepts every legitimate cryptographic use it must not block

## Scope

- `src/cadrumo/core/tests/test_hashing_adoption.py`

## Description

- Add `test_recurrence_gate_flags_a_new_reducible_body_and_allows_legitimate_uses`: the discrimination (anti-tautology) proof for the hashing recurrence gate.
- Assert the gate's own `_reducible_one_shot_sites` detector FLAGS every reducible shape: `sha256(payload).hexdigest()`, `hashlib.sha256(text.encode(...)).hexdigest()`, and a truncated `hashlib.sha256(payload).hexdigest()[:16]`.
- Assert the detector NEVER flags the non-substitutable cryptographic uses the ADR protects: incremental/streaming (`sha256()` + `.update()` + `.hexdigest()`), raw digest-byte (`.digest()[0]`), keyed HMAC (`hmac.new(..., sha256).hexdigest()`), key derivation (HKDF), and X509 fingerprint (`certificate.fingerprint(hashes.SHA256())`).

## Outcome

The proof runs the SAME detector the S04 gate runs, over synthetic sources, so the gate cannot silently pass green while its detector is broken — a reducible body is provably caught and every allowed use provably passes. This is the "rejects a new reducible one-shot body and accepts every legitimate cryptographic use it must not block" evidence the step requires. 3 tests pass in the file; ruff clean.

## Notes

Shares the production gate's exact detector (no parallel reimplementation that could drift), matching the discrimination-proof standard applied to the select_revision gate (P09.S23) and the false-green-runner lesson. No production code changed.
