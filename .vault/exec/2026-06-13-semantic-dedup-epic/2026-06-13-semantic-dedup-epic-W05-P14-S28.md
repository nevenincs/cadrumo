---
tags:
  - '#exec'
  - '#semantic-dedup-epic'
date: '2026-06-14'
modified: '2026-06-15'
step_id: 'S28'
related:
  - "[[2026-06-13-semantic-dedup-epic-plan]]"
---




# C2-2 Extract a parameterized uppercase-alpha and unique-tuple validator factory and route the copies through it

## Scope

- `src/aeat/domain/calculations/registry/_binding_selector_utils.py`

## Description

- Verified the pydantic v2 `field_validator(...)(factory("label"))` wiring in a
  standalone check before touching production (no factory-validator precedent
  in the codebase).
- Added `uppercase_alpha_code(label)` and `unique_tuple(label)` factories to
  `_binding_selector_utils` (with `RegistryValidationError`).
- Routed 7 uppercase-alpha validators (invoice, counterpart, withholding,
  detail_record x4) and 4 pure unique-tuple validators (invoice, counterpart,
  withholding, previous_filing) through the factories via the assignment form.
- Left the clave validators and invoice `_claves_uppercase_unique` in place
  (constraint-divergent: extra AEAT clave-membership check).

## Outcome

Committed as `ea84618ce`, tagged `relocation:uppercase_alpha_code` (6 files,
+55/-74). Ruff clean; 368 registry binding/observation tests green.

## Notes

The unified message `"<label> must be uppercase alphabetic"` satisfies every
existing assertion: the two two-`if` sites' tests match `"country_code must be
uppercase"` as an `re.search` substring, and the detail_record tests match the
full label-specific string exactly (labels chosen as country_code / "ISO code"
/ member_state_code to match). Behaviour (accept/reject set) is identical; only
the granular two-message wording on two sites collapsed to one.
