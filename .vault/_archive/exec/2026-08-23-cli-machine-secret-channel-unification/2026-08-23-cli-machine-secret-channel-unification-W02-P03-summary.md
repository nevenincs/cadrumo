---
tags:
  - '#exec'
  - '#cli-machine-secret-channel-unification'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:a78c7e0b923e9ae64248ec526cbccb297fe487c49f7aa07491abd60a9bb18ea1'
related:
  - "[[2026-08-23-cli-machine-secret-channel-unification-plan]]"
---

# `cli-machine-secret-channel-unification` `W02.P03` summary

## Description

Migrated login and profile creation to the canonical paired channels, retained verified-terminal prompts, preserved credential-policy and mutation ordering, and removed CLI environment, settings, keyring, and manual-injection fallback paths.

- Modified: `src/cadrumo/entrypoints/cli/_config/_custody.py`
- Modified: `src/cadrumo/entrypoints/cli/_config/_scripted_registration.py`
- Modified: `src/cadrumo/entrypoints/cli/_config/_manager_dispatch.py`
