---
tags:
  - '#exec'
  - '#cli-machine-secret-channel-unification'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:85f3a2b7a8f5490cf77840899bc4527195b0d48728c84e1bf12a1b3fcf5426ac'
step_id: 'S13'
related:
  - "[[2026-08-23-cli-machine-secret-channel-unification-plan]]"
---

# Run vaultspec-rag semantic code and ADR discovery, confirm exact symbols with rg, then re-read current HEAD, status, and scoped diff, and add real subprocess success coverage for stdin and inherited descriptors across all five leaf commands and both restore doors plus keychain-free root profile authentication on representative read and write commands, certificate dual-source combinations, fd0, closure, prompt absence, Windows HANDLE bootstrap, and leak checks

## Scope

- `src/cadrumo/entrypoints/cli/tests/test_machine_secret_channels_subprocess.py`

## Description

- Ground the matrix in the accepted transport ADR, both research records, the
  settled leaf migrations, the amended root-authentication records, semantic
  discovery, exact source searches, and current-HEAD inspection.
- Drive the production `main()` boundary in fresh interpreters against real
  encrypted profile storage for login, creation, rotation, both restore doors,
  certificate-secret mutation, and profile-bound reads.
- Exercise portable stdin on every leaf and POSIX anonymous inherited pipes on
  every leaf, including fd 0, one-shot descriptor closure, all valid
  certificate root/leaf source combinations, and two distinct descriptors.
- Exercise keychain-free per-invocation authentication for a real read and a
  real certificate-registry/write sequence, including the non-persistence
  Notice and absence of interactive prompting or secret disclosure.
- Exercise Windows through an allowlisted inherited HANDLE and the production
  HANDLE-to-CRT bootstrap for root, leaf, and dual-secret invocations without
  asserting POSIX numeric descriptor inheritance parity.
- Scan stdout, stderr, and diagnostic log files for every planted secret and
  run focused subprocess, Ruff, format, type, compile, and Vault gates.

## Outcome

The success matrix now crosses fresh process, real CLI, real application, and
real encrypted-storage boundaries. All seventeen subprocess scenarios pass on
Windows with no skip: STARTUPINFOEX allowlists inherited HANDLEs, the production
bootstrap maps root and leaf HANDLEs independently, and the child proves every
mapped CRT descriptor closes after its canonical one-shot read. The same matrix
uses `pass_fds`, anonymous pipes, child-side closure assertions, fd 0, and all
three valid dual-source combinations on POSIX.

The keychain is deliberately forced unavailable. Successful root authentication
continues the parsed read and write in-process, carries
`config.login.session_not_persisted`, and never emits the planted profile,
replacement, or certificate secrets. Explicit-channel success in a captured
non-terminal also proves no prompt was reached.

## Notes

- Windows uses the explicit HANDLE allowlist/bootstrap contract for every
  inherited descriptor scenario; POSIX uses numeric `pass_fds`. Neither test
  path claims those process-inheritance mechanisms are interchangeable.
- A concurrent peer temporarily left `_terminal_errors.py` syntactically
  incomplete during one matrix run. No peer file was edited; after the peer
  restored a compilable tree, the scoped matrix reran cleanly.
- The shared worktree contains unrelated in-flight release, registry, S15, and
  terminal-error work. This Step owns only its test module, execution record,
  review audit, plan checkbox, and feature index refresh.
