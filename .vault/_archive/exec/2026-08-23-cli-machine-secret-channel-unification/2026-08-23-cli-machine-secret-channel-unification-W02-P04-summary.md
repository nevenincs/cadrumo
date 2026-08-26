---
tags:
  - '#exec'
  - '#cli-machine-secret-channel-unification'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:a18cf3465a2709b4af6ea1f0299e89bdfad286dbf68ce901def3e5f81322579d'
related:
  - "[[2026-08-23-cli-machine-secret-channel-unification-plan]]"
---

# `cli-machine-secret-channel-unification` `W02.P04` summary

## Description

Migrated passphrase rotation, both restore doors, and certificate-secret storage to the shared transport capability. The migration hard-cut restore `password` to `passphrase` and certificate `secret` to `certificate_passphrase` without aliases or compatibility shims.

- Modified: `src/cadrumo/entrypoints/cli/_config/_passphrase.py`
- Modified: `src/cadrumo/entrypoints/cli/_config/_restore_cli.py`
- Modified: `src/cadrumo/entrypoints/cli/_config/_certificate.py`
