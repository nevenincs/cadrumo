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

# audits-resolution group-c step-4

## scope

Plan row C4: rewrite the Quickstart line under `aeat --help` to drop
the optional `--profile-name` flag and include the required
`--activity` flag.

## changes

Locale catalogues `es / en / ca / hu` flip the Quickstart line under
`root.app_help` from
`Quickstart: aeat config init --profile NAME --tax-id NIF`
to
`Quickstart: aeat config init --tax-id NIF --activity ACTIVIDAD`
(es / en localised, ca / hu mirror the English shape).

`src/aeat/entrypoints/cli/test_workflow_surface.py` updates the
`test_root_no_args_renders_help_successfully` assertion to match
the new Quickstart shape.

## verification

`aeat --help` against the project sandbox renders the new
Quickstart line. The corresponding workflow-surface test asserts
against the new substring shape.
