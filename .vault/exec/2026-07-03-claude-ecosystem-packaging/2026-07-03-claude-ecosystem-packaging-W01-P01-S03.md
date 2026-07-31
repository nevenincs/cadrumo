---
tags:
  - '#exec'
  - '#claude-ecosystem-packaging'
date: '2026-07-03'
modified: '2026-07-17'
body_hash: 'sha256:f92110b35ca35326653865b2ed5b91241eb28575f3367062d7195971c1b49080'
step_id: 'S03'
related:
  - "[[2026-07-03-claude-ecosystem-packaging-plan]]"
---

# Assert the derived tokens, logs, secret, blob and audit roots follow the installed platform base through the existing state-root validators

## Scope

- `src/aeat/core/tests/test_config_state_root.py`

## Description

- Add `src/aeat/core/tests/test_config_state_root.py` asserting the derived tokens, logs, secrets, blobs, and audit roots re-derive under the installed platform base.
- Confirm the re-derivation flows through the existing state-root validators: `default_factory` leaves the field unset so the `model_fields_set`-keyed validators re-derive it from the platform-resolved storage root rather than a stale default.
- Commit `83baff4254`.

## Outcome

- New test module passes, exercising the derived-root re-computation for every dependent state directory.

## Notes

No incidents. No skipped work.
