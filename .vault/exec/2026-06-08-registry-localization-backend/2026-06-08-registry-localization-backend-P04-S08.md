---
tags:
  - '#exec'
  - '#registry-localization-backend'
date: '2026-06-08'
modified: '2026-06-08'
related:
  - '[[2026-06-08-registry-localization-backend-plan]]'
---

# `registry-localization-backend` `P04.S08` execution record

Create local translation files under model-level and revision-level locales folders.

## Action

Created translation files (`en.toml`, `ca.toml`, and `hu.toml`) under `src/aeat/_data/registry/aeat/modelos/130/revisions/2019-y-siguientes/locales/` containing localized labels and help texts for Casillas 01-07.

## Verification

Locales are validated during registry loading at compile time, and no errors or warnings are generated.
