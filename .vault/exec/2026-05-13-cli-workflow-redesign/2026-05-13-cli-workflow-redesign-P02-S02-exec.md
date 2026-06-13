---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
step_id: 'P02.S02'
related:
  - "[[2026-05-13-cli-workflow-redesign-config-repair-shape-plan]]"
---

# `cli-workflow-redesign` `P02.S02`

Extended `DiagnosticCheck._enforce_actionable_contract` to require
exactly one of `next_action` or `dead_end` for `status in {"fail",
"warn"}` and to forbid either field on `status == "ok"` rows.

- Modified: `src/aeat/application/diagnostics.py`

## Description

The validator implements the strict reading of the ADR's row table:

- `ok` rows carry neither recovery field.
- `fail` and `warn` rows carry exactly one of `next_action`
  (a runnable `aeat …` command) or `dead_end` (a short reason no
  automated route exists).

Two existing source-side fail-row constructions (`registry.load`
fail and `secure_state.load` fail) carried neither recovery field
and would have raised `ValidationError` at runtime under the new
contract. Both received minimal `dead_end` placeholders so the
diagnostic remains constructible until P04 wires the ADR-mandated
mapping; the temporary copy is explicitly marked as "wired by P04".

## Confirmation

- New tests assert `ValidationError` for fail / warn rows missing
  recovery, and for `ok` rows that advertise recovery.
- `build_config_doctor_report()` happy path remains green.
