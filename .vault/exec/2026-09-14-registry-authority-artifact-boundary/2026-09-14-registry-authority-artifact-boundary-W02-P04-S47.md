---
tags:
  - '#exec'
  - '#registry-authority-artifact-boundary'
date: '2026-09-14'
modified: '2026-09-14'
body_schema: 'body-v2'
body_hash: 'sha256:1912b4a2aa79699fdfb2a4a8a4965b29a73aca6e7ae966fe18e0fd8fd694069a'
step_id: 'S47'
related:
  - "[[2026-09-14-registry-authority-artifact-boundary-plan]]"
---
# Migrate the listed auth, wizard, diagnostics and profile aggregation consumers plus domain/renta/maritime_exemption.py and dev/locales/_registry_scanner.py with their owning fixtures

## Scope

- `profile schema consumer migration`

## Changes

- `M` `src/cadrumo/application/auth/sessions.py`
- `M` `src/cadrumo/application/wizard/status.py`
- `M` `src/cadrumo/application/diagnostics.py`
- `M` `src/cadrumo/domain/renta/maritime_exemption.py`
- `M` `dev/locales/_registry_scanner.py`
- `verify:` `checkpoint B integrated profile selection` -> `pass`
