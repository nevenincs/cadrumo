---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-18'
modified: '2026-08-18'
body_schema: 'body-v1'
body_hash: 'sha256:4c72dfe97aef641a16cd40fab7114a85c0a416c5fedf03d536910b7ed1054f31'
step_id: 'S194'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh stop the two advisory paths that refuse or crash on states an operator legitimately passes through, the manager overview projecting a taxpayer classification without guarding the validation error a half-entered non-resident record raises so declaring non-residency before a country crashes the screen and blocks that onboarding outright, and the descendants advisory embedding an executable invocation in a notice message where the envelope contract admits one only through its typed action projection

## Scope

- `src/cadrumo/entrypoints/cli/_config/_status_frontend.py and src/cadrumo/application/wizard/_commands.py`

## Description

## Outcome

Both advisory paths are fixed (commits `a6c9d9fb90`, locale follow-up). The manager overview's no-AEAT-history projection now guards `derive_tax_route(projection_for_taxpayer(record))` against `ValidationError` — a half-entered non-resident record (residency declared, country not) degrades to the generic advisory with `tax_route=None` instead of crashing the status page (the sibling `_overview.py` degrade precedent). The descendants advisory no longer interpolates an executable command string into the notice message: `command=` and the `'{command}'` placeholder are gone from the tr() calls and from all four catalogues, and the door now rides the typed action projection — a new `operator.profile.descendiente` catalogue entry (`target_command_key="config.profile.descendiente"`) resolved through `next_action`, so a renamed verb fails closed at emission instead of shipping a dead instruction. The honesty test asserts the nested `notice["action"]["action"]` shape; wizard command-helper suite 23 passed, honesty 7 passed.

## Notes

Routed finding: `test_status_frontend_gate.py` fails 4 cases at HEAD asserting `StatusPageData.recovery` — the recovery-zone model was never landed while the committed test expects it (peer WIP left half-committed); pre-existing, not this row's. The half-entered non-resident regression rides the guard via the existing degrade test's empty-root path.
