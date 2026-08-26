---
tags:
  - '#exec'
  - '#cli-machine-secret-channel-unification'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:d1350eac9db40e14ea2d95fc038a2ca8a5f805ab3ec45cf80c222c3ad892553c'
related:
  - "[[2026-08-23-cli-machine-secret-channel-unification-plan]]"
---

# `cli-machine-secret-channel-unification` `W02.P11` summary

## Description

Restored the self-authenticating rotation verb and added distinct root profile-proof channels for keychain-free per-invocation operation. Dispatch now validates root and leaf sources before reading, authenticates the exact target only after resume failure, refuses unused or colliding sources, and preserves bounded cleanup and platform-specific descriptor transfer.

- Created: `src/cadrumo/entrypoints/cli/_profile_authentication_contract.py`
- Created: `src/cadrumo/entrypoints/cli/_profile_authentication_gate.py`
- Modified: root and custody command specifications, session integration, locales, and focused tests
