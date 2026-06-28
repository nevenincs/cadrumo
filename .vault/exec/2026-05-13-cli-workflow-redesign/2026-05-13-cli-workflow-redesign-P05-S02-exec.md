---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
step_id: 'P05.S02'
related:
  - "[[2026-05-13-cli-workflow-redesign-config-repair-shape-plan]]"
---

# `cli-workflow-redesign` `P05.S02`

Removed the obsolete `cli.config.doctor.*` block (9 keys) from the
Spanish locale catalogue. The `cli.config.repair.*` block already in
place carries the operator-facing Spanish copy (e.g. `"Diagnosticar y
reparar configuración local …"`). The `quick_start_doctor` root-
landing key remains until P06 retargets the Python lookup site;
its value already references `aeat config repair`.

- Modified: `src/aeat/locales/es.yml`

## Tests

YAML parse round-trip clean.
