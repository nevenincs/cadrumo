---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:ff37aa8e60a1705916ee539c36ca01c5482c298144394c09b5283e946b87023e'
step_id: 'S37'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---
# Replace wizard refusal and next-action command authority with canonical typed projections

## Scope

- `src/cadrumo/application/wizard`
- `src/cadrumo/application/tests/test_diagnostics_dispatch.py`

## Description

- Add standard terminal transport and canonical no-action verdicts to status, missing-input, label, and console refusals.
- Replace wizard next-action command strings with typed declared actions.
- Remove the unreachable profile-create save/resume emitter, checkpoint carrier, execution branch, exports, and documentation.
- Prove current custody rejects create before console and never recommends interactive profile-create recovery.
- Add exact ten-carrier and whole-production command-authority gates with full runtime contracts.

## Outcome

All ten owned wizard refusal carriers are typed with exact condition, fact-expression, provenance, and outcome contracts. `_next_wizard_action` declares only the fully bound canonical `operator.auth.login` action where applicable and otherwise returns `None`; it contains no executable command authority.

The obsolete create save/resume and checkpoint subsystem is removed without a compatibility field or empty-string coercion. The diagnostics consumer uses `next_action=None`. A whole-wizard structural gate rejects executable `aeat config profile create` recommendations and every retired emitter/carrier symbol.

The focused affected suite passes 139 tests with five marker-deselected cases; independent terminal/diagnostics verification passes 28. Scoped Ruff and diff checks pass, and independent review found no remaining residue.

## Notes

- The existing `_checkpoint_store.py` filename remains solely as the home of live descendant-clearing facts; it contains no retired checkpoint store or save/resume behavior.
