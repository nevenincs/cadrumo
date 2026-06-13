---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
step_id: 'P04.S05'
related:
  - "[[2026-05-13-cli-workflow-redesign-config-repair-shape-plan]]"
---

# `cli-workflow-redesign` `P04.S05`

Set `dead_end="registry is bundled with aeat; reinstall the package
to recover."` on the `registry.load` fail branch and dropped the P02
placeholder string. The registry ships inside the wheel; there is no
runtime self-heal route, so the dead-end branch is the correct
discriminated-union arm per ADR row mapping.

- Modified: `src/aeat/application/diagnostics.py`

## Tests

`pytest src/aeat/application/test_diagnostics.py` 15 passed.
