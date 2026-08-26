---
tags:
  - '#exec'
  - '#cli-machine-secret-channel-unification'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:f6d1e4146d3f603881f3941d24e0ac4d30141393ae87f2e0b89cb04657714937'
step_id: 'S14'
related:
  - "[[2026-08-23-cli-machine-secret-channel-unification-plan]]"
---

# Run vaultspec-rag semantic code and ADR discovery, confirm exact symbols with rg, then re-read current HEAD, status, and scoped diff, and extend the real subprocess matrix with same-scope and cross-scope conflict before read and mutation, invalid descriptor and payload cases, size bounds, old-field refusal, hostile-environment non-interference, valid-session non-consumption, wrong or absent target refusal, self-authenticating exemptions, prompt-only TTY behavior, and four-locale snapshots

## Scope

- `src/cadrumo/entrypoints/cli/tests/test_machine_secret_channels_subprocess.py`

## Description

- Ground the refusal matrix in the accepted transport ADR, both research records,
  the settled S13 success harness, current command graph, canonical readers, root
  gate, and Windows HANDLE bootstrap.
- Exercise leaf and root same-scope exclusivity and both cross-scope collision
  shapes with post-dispatch byte readback proving stdin and descriptors remained
  untouched before parsing, KDF work, session activation, or mutation.
- Exercise reserved, unreadable, malformed, duplicate, missing, extra, empty, and
  valid-JSON oversize inputs with typed diagnostic partitions, planted-secret leak
  checks, descriptor closure, and durable-state snapshots.
- Exercise retired restore and certificate fields, hostile environment input,
  exact-target ordering, blank and wrong authentication, live-session
  non-consumption, self-authenticating exemption, help and parse precedence, and
  four localized conflict snapshots.
- Correct the Windows equal-HANDLE ownership route so one backing channel becomes
  one CRT descriptor at both scopes and cleanup never double-closes it.
- Parse every JSON refusal envelope and require typed error shape, exact public
  category evidence, prompt absence, secret-free output and logs, and either
  byte-for-byte storage stability or the explicitly authenticated refusal path.
- Run independent SOL review, remediate both HIGH and all MEDIUM findings, and
  rerun the complete settled module.

## Outcome

The real-process refusal matrix now proves the inverse of S13's success contract.
All five leaf commands and the distinct root scope refuse ambiguous channels before
consumption; Windows preserves equal-HANDLE identity through bootstrap; malformed
inputs close channels after read; inapplicable and parse-precedence inputs remain
available for caller recovery; and no planted secret reaches envelopes, prompts, or
diagnostic logs.

The final current-tree module passed all 67 cases in 647.10 seconds on Windows.
Focused canonical-reader tests passed 23 cases, the related lifecycle collision and
terminal-introspection partition passed four cases, Ruff and formatting passed, and
targeted static analysis reported zero errors or warnings. Independent SOL review
found two HIGH and nine MEDIUM oracle gaps; every finding was remediated and the
reviewer's final current-tree reread found no new medium-or-higher issue.

## Notes

- A serialized shared-tree writer captured the first S14 test tranche in mixed
  commit `af1b7f21bba`; the final scoped close commit carries the remaining runtime
  remediation and lifecycle records. The effective source review covered both.
- Concurrent source-mesh edits temporarily made the repository unimportable at two
  collection attempts. No peer file was changed; verification resumed only after
  the peer restored a coherent import graph.
- The Windows oversize case uses a temporary inherited file descriptor because a
  synchronous pre-spawn write larger than the platform pipe capacity blocks before
  the child can drain it. Ordinary descriptor cases retain anonymous pipes.
- POSIX numeric-descriptor branches remain encoded through `pass_fds` and the same
  readback oracles; this Windows run does not claim direct execution on POSIX.
