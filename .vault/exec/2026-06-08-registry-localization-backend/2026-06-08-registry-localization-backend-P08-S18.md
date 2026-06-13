---
tags:
  - '#exec'
  - '#registry-localization-backend'
date: '2026-06-08'
modified: '2026-06-08'
related:
  - '[[2026-06-08-registry-localization-backend-plan]]'
---

# `registry-localization-backend` `P08.S18` execution record

Map localized labels and help text files for Modelo 100, Modelo 200, and Modelo 303 under `src/aeat/_data/registry/aeat/modelos/`.

## Action

Created translation files (`ca.toml`, `en.toml`, `hu.toml`) under:
- `src/aeat/_data/registry/aeat/modelos/100/revisions/2024/locales/`
- `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/locales/`
- `src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/locales/`
Mapping keys to translatable labels and help text invariants.

## Verification

Enforced by locales compiler and verified via locales parity test.
