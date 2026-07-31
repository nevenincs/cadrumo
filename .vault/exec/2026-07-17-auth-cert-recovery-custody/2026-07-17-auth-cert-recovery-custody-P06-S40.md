---
tags:
  - '#exec'
  - '#auth-cert-recovery-custody'
date: '2026-07-19'
modified: '2026-07-19'
body_hash: 'sha256:43bd271579712a701fc10406e55cd558c3a858eeb4fb0fc6d8773e79aa483102'
step_id: 'S40'
related:
  - "[[2026-07-17-auth-cert-recovery-custody-plan]]"
---

# Prove the removed auth, certificate, and recovery spellings are absent from every source and generated surface

## Scope

- `src/cadrumo/entrypoints/cli/tests/test_root_grammar_invariants.py`

## Description

- Extend `test_root_grammar_invariants.py`: the retired spellings (`rekey`, `show-recovery`, `verify-recovery`) do not resolve; no recovery verb accepts a mnemonic/passphrase argv option; `config recovery` mounts exactly status/create/rotate/verify.
- Add a source-and-docs sweep asserting the retired spellings (including `--recovery-key` and `config rekey`) are absent from the Python tree, the four locale catalogues, the operator docs, and the sequence contracts, exempting only the rejection-probe tests that exist to prove refusal.

## Outcome

Grammar invariants green; the sweep caught and drove out the last stragglers in the master-key error texts, storage tests, and locale copy.

## Notes

None.
