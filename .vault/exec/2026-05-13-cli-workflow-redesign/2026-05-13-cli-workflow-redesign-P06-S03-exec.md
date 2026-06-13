---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
step_id: 'P06.S03'
related:
  - "[[2026-05-13-cli-workflow-redesign-config-repair-shape-plan]]"
---

# `cli-workflow-redesign` `P06.S03`

Replaced the `aeat config doctor` default suggestion on the
`LedgerStorageError` row with the redesigned namespace, and confirmed
the analogous `SecureObjectUnreadableError` row in `_adapters.py`
already points at the bucket-quarantine remediation route.

- Modified: `src/aeat/core/errors/registry/_domain.py`
- Inspected (already at target value): `src/aeat/core/errors/registry/_adapters.py`

## Description

The `LedgerStorageError` row (FAIL category, ledger storage
persistence) is a generic storage-health hint: nothing about the
condition pins it to either workflow-state-envelope corruption or
secure-object integrity. Per the ADR's specific-subcommand mapping
this row points at the composite report `aeat config repair`. The
prior literal `"aeat config doctor"` is replaced with
`"aeat config repair"` in the `default_suggestion` field of the
matching `ErrorCode` block in `_domain.py`.

The `SecureObjectUnreadableError` row in `_adapters.py` is exactly
secure-object integrity by definition, so it points at
`aeat config repair quarantine --yes`. The literal was already
present in HEAD from a prior P-step commit; no re-edit was required.

No test assertion in `src/aeat/core/errors/` or
`src/aeat/entrypoints/cli/test_error_registry_contract.py` pins
either of these specific hint strings, so no test fixture changes
were required.

## Tests

`pytest src/aeat/core/errors/` was re-run after the edit. The single
surviving failure
(`test_every_registered_code_maps_to_exactly_one_error_subclass`)
relates to broader registry-restructuring WIP currently outside the
P06 scope and is not introduced by this step.
