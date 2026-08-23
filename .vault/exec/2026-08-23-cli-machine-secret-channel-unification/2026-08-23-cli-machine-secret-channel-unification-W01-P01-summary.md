---
tags:
  - '#exec'
  - '#cli-machine-secret-channel-unification'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:4c3fb2d16528d561ffc3bc9b828a60cd37895a7366fd387150f08c20e753c533'
related:
  - "[[2026-08-23-cli-machine-secret-channel-unification-plan]]"
---

# `cli-machine-secret-channel-unification` `W01.P01` summary

## Description

Established `_secure_input` as the single bounded, strict, one-shot reader and selector for stdin and descriptor payloads. Its focused tests cover strict JSON, bounds, duplicate and extra fields, descriptor zero, reserved descriptors, closure, one-shot behavior, and secret-free refusals.

- Modified: `src/cadrumo/entrypoints/cli/_config/_secure_input.py`
- Created: `src/cadrumo/entrypoints/cli/_config/tests/test_secure_input_machine_channels.py`
