---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
step_id: 'P07.S04'
related:
  - "[[2026-05-13-cli-workflow-redesign-config-repair-shape-plan]]"
---

# `cli-workflow-redesign` P07.S04 — secure_objects runtime hint and docstrings now name `aeat config repair`

## Finding

H-2 (HIGH). `src/aeat/adapters/persistence/storage/sql/secure_objects.py`
still pointed operators at the retired `aeat config doctor` command:
the warning-log line emitted by `list_records` when undecryptable rows
are skipped, and the module-level docstrings on the integrity-probe
methods used the same label.

## Resolution

Replaced `(run 'aeat config doctor' for details).` on the WARN log line
with `(run 'aeat config repair' for details).`. Updated the two
docstring mentions of `aeat config doctor` on `probe_namespace_integrity`
and the surrounding integrity contract to read `aeat config repair`.

## Verification

`pytest src/aeat/application/test_diagnostics.py` exercises the probe
path indirectly via `build_config_repair_report` and stays green.
