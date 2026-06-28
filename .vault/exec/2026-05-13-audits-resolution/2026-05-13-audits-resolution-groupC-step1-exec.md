---
tags:
  - '#exec'
  - '#audits-resolution'
date: '2026-05-13'
modified: '2026-05-13'
related:
  - "[[2026-05-13-audits-resolution-plan]]"
  - "[[2026-05-13-schema-driven-wizard-ux-audit]]"
---

# audits-resolution group-c step-1

## scope

Plan row C1: group `aeat config init --help` flags by descriptor
section via Typer's `rich_help_panel` so the 42-flag surface renders
as one panel per `WizardSection` rather than a single
ellipsis-truncated column.

## change

`src/aeat/application/wizard/_commands.py`:

- `_python_parameter` gains an optional `section_title: str | None`
  keyword. The title is threaded into every `typer.Option` instance
  the function builds (CONFIRM, SELECT, CHECKBOX, INTEGER, PATH,
  SECRET, TEXT) as `rich_help_panel=section_title`.
- `_question_parameters` resolves each section's translated title
  via `tr(str(section.title))` and threads it through every
  question's `_python_parameter` call.

The mode flags (`--profile`, `--quiet`, `--accept-defaults`) stay in
the default `Options` panel; only the wizard-derived flags receive
the per-section panel.

## verification

`pytest src/aeat/application/wizard/ -q`: 160 passed.

Live invocation of `aeat config init --help` against a sandbox
renders one panel per descriptor section: "Identidad del perfil",
"Primer declarante", "Cónyuge", "Unidad familiar", "IVA",
"Inscripción", "Obligaciones", "Residencia fiscal", "Notas". The
column wrapper still ellipsises a handful of the longest spouse /
family flag names, but operators can now read the panel structure
and know which sections to copy from.
