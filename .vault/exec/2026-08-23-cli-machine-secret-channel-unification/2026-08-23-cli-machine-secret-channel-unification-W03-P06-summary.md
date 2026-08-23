---
tags:
  - '#exec'
  - '#cli-machine-secret-channel-unification'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:bc89f425bfb389c0b2c2e53c66e930ad7e61e4f96f18112b505d41af6630db1a'
related:
  - "[[2026-08-23-cli-machine-secret-channel-unification-plan]]"
---

# `cli-machine-secret-channel-unification` `W03.P06` summary

The real subprocess phase proves both successful and refused machine operation
through the production CLI, application, encryption, and storage boundaries.

- Modified: `src/cadrumo/entrypoints/cli/tests/test_machine_secret_channels_subprocess.py`
- Modified: `src/cadrumo/entrypoints/cli/_windows_profile_secret_bootstrap.py`
- Modified: `src/cadrumo/entrypoints/cli/tests/test_config_custody_profile_lifecycle.py`
- Created: `2026-08-23-cli-machine-secret-channel-unification-W03-P06-S13.md`
- Created: `2026-08-23-cli-machine-secret-channel-unification-W03-P06-S14.md`

## Description

S13 established portable stdin success for every scalar-secret leaf, inherited
descriptor success for every leaf and both restore doors, keychain-free root
authentication for real reads and writes, fd 0, dual-source composition,
one-shot closure, Windows allowlisted HANDLE conversion, prompt absence, and
secret-free output and logs.

S14 established the matching refusal boundary: same-scope and cross-scope
conflicts before consumption, KDF, session, or mutation; typed descriptor and
strict-payload failures; hard-cut legacy fields; hostile environment
non-interference; exact-target and session applicability; help and parse
precedence; four-locale diagnostics; and durable-state and channel-lifecycle
oracles. Independent SOL review drove two HIGH and nine MEDIUM corrections,
including single-conversion identity for equal Windows HANDLEs. All findings
are closed. The settled module passed 67 integration cases in 647.10 seconds;
canonical-reader and related lifecycle partitions also passed.
