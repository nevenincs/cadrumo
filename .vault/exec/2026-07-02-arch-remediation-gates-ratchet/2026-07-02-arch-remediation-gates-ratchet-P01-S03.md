---
tags:
  - '#exec'
  - '#arch-remediation-gates-ratchet'
date: '2026-07-02'
modified: '2026-07-17'
body_hash: 'sha256:0c54048666ddb2455c52bb0a6f085bc5ae71602030a8e6ca1c3d7bdad3db41d9'
step_id: 'S03'
related:
  - '[[2026-07-02-arch-remediation-gates-ratchet-plan]]'
---

# Re-file wrong-contract ledger entries

## Scope

- `.importlinter`

## Description

- Re-verified the contract sections before editing and treated Import Linter's unmatched-entry failures as the source of truth for wrong-scope entries.
- Re-filed the live `aeat.domain.usage_ratios._service -> aeat.adapters.persistence.storage.runtime_repository` edge into the layered contract.
- Removed wrong-contract placements that were stale under `unmatched_ignore_imports_alerting = error`.

## Outcome

One live ignore edge changed contract scope. No stale wrong-contract entries remain in the passing `lint-imports` run.

## Notes

The S21/S22/S23 narrative headers remain descriptive only; the executable contract association is the parsed section containing each ignore entry.
