---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
step_id: 'P05.S04'
related:
  - "[[2026-05-13-cli-workflow-redesign-config-repair-shape-plan]]"
---

# `cli-workflow-redesign` `P05.S04`

Removed the obsolete `cli.config.doctor.*` block (9 keys) from the
Hungarian locale catalogue. The `cli.config.repair.*` block already
carries the Hungarian copy (uses `javítás` for the natural metaphor
and `repair` for the command verb). The `quick_start_doctor` landing
key remains until P06.

- Modified: `src/aeat/locales/hu.yml`

## Tests

YAML parse round-trip clean.
