---
tags:
  - '#exec'
  - '#profile-registration-password-policy'
date: '2026-08-22'
modified: '2026-08-22'
body_schema: 'body-v1'
body_hash: 'sha256:a81565763ae930a6c2ea58621f2901348ee1ab0dd68648b83984dde86b3880f8'
step_id: 'S05'
related:
  - "[[2026-08-22-profile-registration-password-policy-plan]]"
---

# Ground code and governing ADRs with vaultspec-rag, confirm exact symbols with rg, reread HEAD, inspect overlapping diffs, then make custody consume the canonical contract, remove duplicate constants and exports, and prove strict defense-in-depth boundaries plus obsolete-symbol absence

## Scope

- `src/cadrumo/adapters/persistence/storage/custody`

## Description

- Ground custody password and recovery paths against the accepted core contract
  and confirm duplicate limits, validators, consumers, and exports exactly.
- Replace custody-owned policy with private strict UTF-8 transport adapters that
  consume the canonical core assessment.
- Map each typed canonical refusal to a non-presentational, secret-free custody
  diagnostic before supervised KDF work.
- Delete duplicate custody limits and public and transitive password validator
  exports without aliases or fallback policy.
- Prove scalar, byte, surrogate, exact Unicode, strict transport, facade absence,
  and recovery-preservation behavior with real custody tests.

## Outcome

- Core exclusively owns profile-password validity while custody retains
  defense-in-depth enforcement at both parent and worker boundaries.
- Accepted passwords preserve exact UTF-8 bytes; composed and decomposed forms
  remain distinct and unmodified.
- Every canonical refusal reason maps without including candidate contents or
  measurements, and malformed UTF-8 transport remains refused.
- All 13 focused record tests and all 207 custody tests pass; 207 custody tests
  collect cleanly with 10 excluded only by the repository marker selection.
- Ruff, diff hygiene, public-facade probes, and feature Vaultspec checks pass.

## Notes

The generic supervised material wrapper remains shared by password and recovery
callers, so recovery mnemonics still traverse the private profile-password codec
without changing their bytes. Splitting the parent and worker recovery-secret
codec is the ordered S06 task; changing that shared wire operation here would
either break recovery or overlap its dedicated roundtrip scope.
