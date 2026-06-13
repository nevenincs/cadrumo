---
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-31'
modified: '2026-05-31'
step_id: 'S537'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
---

# `codebase-solidification` `W08.P34.S537`

WRAP: `profile` and `active_profile` tab-key output labels in `wizard/_commands.py` through `tr()`, adding locale keys to all 4 locale files via the locale CLI.

- Modified: `src/aeat/application/wizard/_commands.py`
- Modified: `src/aeat/locales/en.yml`, `es.yml`, `ca.yml`, `hu.yml`

## Description

Two bare string labels (`"profile"` and `"active_profile"`) in the wizard output path were wrapped with `tr("application.wizard.output_labels.profile")` and `tr("application.wizard.output_labels.active_profile")`. The `status` tab-key value remained untranslated as it is a machine-format key, not a user-visible label.

Locale keys were added under `application.wizard.output_labels` in all four locale files via `python -m aeat.locales scaffold` and `audit`. Values defaulted to the English key name (`"profile"` / `"active_profile"`) in all locales as placeholder-free sentinels awaiting translation.

Grep-post-condition: `grep -n '"profile"\|"active_profile"' src/aeat/application/wizard/_commands.py` returned 0 bare-label lines.

## Tests

Locale audit (`python -m aeat.locales audit`) reported zero missing keys. Existing wizard command tests passed.
