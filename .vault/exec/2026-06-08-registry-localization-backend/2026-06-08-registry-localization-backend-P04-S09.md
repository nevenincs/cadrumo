---
tags:
  - '#exec'
  - '#registry-localization-backend'
date: '2026-06-08'
modified: '2026-06-08'
related:
  - '[[2026-06-08-registry-localization-backend-plan]]'
---

# `registry-localization-backend` `P04.S09` execution record

Update CLI command handlers to display localized labels and help texts.

## Action

1. Updated `ModeloCasillaRow` in `src/aeat/domain/calculations/registry/_queries.py` to hold `localized_labels` and `localized_help` dictionaries.
2. Updated `CasillaRowPayload` in `src/aeat/entrypoints/cli/_modelo_payloads.py` to expose `localized_labels` and `localized_help` fields in JSON envelopes.
3. Modified the `casillas` CLI command in `src/aeat/entrypoints/cli/_modelo_discovery_cli.py` to:
   - Accept the `--explain` CLI option.
   - Output localized labels based on the active language (`output_language()`).
   - Output localized help texts when `--explain` is provided.

## Verification

Test the CLI output using language overrides and ensure the output is localized correctly.
