---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
step_id: 'P02.S04'
related:
  - "[[2026-05-13-cli-workflow-redesign-config-repair-shape-plan]]"
---

# `cli-workflow-redesign` `P02.S04`

Extended the text renderer to emit a tab-separated `note\t<reason>`
line for any check carrying a `dead_end`, mirroring the existing
`next\t<cmd>` line for `next_action`.

- Modified: `src/aeat/application/diagnostics.py`

## Description

`render_config_doctor_text` now emits, per check (in order):

- `<status>\t<name>\t<summary>`
- `detail\t<detail>` (optional)
- `next\t<next_action>` (optional)
- `note\t<dead_end>` (optional)

The validator guarantees `next` and `note` are never both emitted
for the same row. Format remains tab-separated key-value lines
consistent with the surrounding tabular style; no whitespace or
newline drift introduced.

The renderer keeps its current name; the rename to
`render_config_repair_text` is owned by P04.

## Confirmation

- `pytest src/aeat/application/test_diagnostics.py::test_render_config_doctor_text_is_operator_readable`
  passes.
