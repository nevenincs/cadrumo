---
tags:
  - '#plan'
  - '#packaged-kdf-attestation'
date: '2026-10-15'
tier: L1
related:
  - '[[2026-10-04-canonical-environment-adr]]'
  - '[[2026-10-13-canonical-environment-application-internals-adr]]'
  - '[[2026-08-13-profile-password-custody-rollup-adr]]'
modified: '2026-10-15'
body_schema: body-v2
body_hash: 'sha256:234fb4a81535091b52773a820512926d40a0a0b8cc74ae54ed49f084a87fd4d1'
---

# `packaged-kdf-attestation` plan

## Description

Approved 2026-10-15

The user authorized fixing the packaged KDF blocker, rebuilding Debug and Release application payloads through CMake without moving build paths or selecting documentation or installer targets, and rerunning both saved proofs with Claude Haiku over API. This plan preserves the remaining work after direct execution crossed a context handoff.

S01 follows the accepted canonical environment declarations and custody supervision decision: the assembler projects package-fixed names from the generated contract into verified bootstrap metadata; the KDF parent attests exactly caller names plus those fixed names. No weaker environment, KDF, or worker fallback is authorized. S02 uses the existing agent proof runner and disposable profile lifecycle, without changing agent source. These accepted decisions cover the change; no new costly decision is introduced.

## Steps

- [ ] `S01` - Verify the KDF fixed-environment correction and rebuild both application payloads through their existing CMake presets; `src/cadrumo/adapters/persistence/storage/custody/, native/interpreter/bootstrap.py, native/tests/package_smoke.py, dev/packaging/native/assemble.py, build/windows-x64/stage/`.
- [ ] `S02` - Run the two saved packaged Claude Haiku API proofs and review profile cleanup and results; `Y:/code/cadrumo-agent-worktrees/main/dev/package_runner/, .vault/exec/, .vault/audit/`.

## Parallelization

Execute serially in this workspace. Complete both CMake builds before starting packaged runtime processes because build quiescence stops those processes. Other sessions editing enrolled source inputs can invalidate CMake snapshots; retry only with the existing consistency guard intact.

## Verification

Require changed-file lint, format and types; the focused custody and native packaging tests; Debug and Release app-payload builds; packaged Python, agent and environment conformance checks; disposable-profile creation and cleanup; and both saved real-provider nonce and queued-followup proofs using Claude Haiku API. Record the actual results and evidence locations. Run required repository gates, separating unrelated existing failures from this correction. Final integrated review must state any unresolved verification.
