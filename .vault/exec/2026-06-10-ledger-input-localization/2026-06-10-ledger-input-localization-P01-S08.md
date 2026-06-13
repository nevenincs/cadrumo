---
tags:
  - '#exec'
  - '#ledger-input-localization'
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S08'
related:
  - "[[2026-06-10-ledger-input-localization-plan]]"
---




# Run pytest --collect-only -q to verify zero collection errors across all six migrated modules

## Scope

- `confirm no surviving local _parse_decimal/_parse_required_decimal definition remains in any of the six migrated files`
- `src/aeat/entrypoints/cli/`

## Description

- Ran `pytest --collect-only -q` over the migrated CLI modules and the new parser test files.
- Swept the six migrated files for surviving local `_parse_decimal`/`_parse_required_decimal` definitions.

## Outcome

Done. Collect-only is clean (51 tests collected on the migrated surface, zero collection errors). The six migrated files carry zero local parse definitions.

## Notes

Deviation from the literal plan criterion ("zero definitions outside `_common.py`"): two definitions survive in `_ledger_support.py`, but they are zero-logic delegators forwarding to the `_common.py` canonical helpers, and they are live (consumed by `_ledger.py`'s business-pct/taxable-base/iva call sites). Single canonical logic is preserved; the criterion wording predates the peer extraction of `_ledger_support`. Documented in the closure audit; optional cosmetic inline left as a future tidy.
