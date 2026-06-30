---
tags:
  - '#exec'
  - '#cli-persona-testimonials'
date: '2026-06-30'
modified: '2026-06-30'
step_id: 'S20'
related:
  - "[[2026-06-30-cli-persona-testimonials-plan]]"
---

# Harden local export evidence receipts and no-official-evidence messaging

## Scope

- `src/aeat/application/modelo/_export.py`

## Description

- Checked whether local export receipts overclaimed filed AEAT evidence.
- Grounded the distinction between local fichero export and AEAT official
  evidence from justificante, declaration consultation, or CSV cotejo surfaces.
- Hardened application result fields, CLI receipt lines, JSON notices, help text,
  and focused tests.

## Outcome

Commit `d2cc0120e` labels successful local exports as
`local_export_not_official_aeat_filing_evidence`, emits an explicit
no-official-evidence notice, and points operators to reconcile/live justificante
pull or filing-record import after external AEAT filing.

## Notes

Focused ruff, application export tests, CLI export tests, locale scaffold, and
locale audit passed. The separate S19 annual Renta verification remains blocked
by unrelated registry validation WIP.
