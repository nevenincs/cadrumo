---
tags:
  - '#exec'
  - '#data-output-standardization'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S15'
related:
  - "[[2026-07-13-data-output-standardization-plan]]"
---

# Rename the CWD-anchored dot-aeat ledger provenance literals to cadrumo marker forms

## Scope

- `src/cadrumo/application/ledger`

## Description

- Read `_build_split_child_transaction`, `_build_merged_transaction` (both
  `_actions_split_merge.py`), and `_transaction_from_command`
  (`_actions_manual.py`) to confirm how the `.aeat-ledger-split` /
  `.aeat-ledger-merge` / `.aeat-manual-ledger` literals are consumed before
  renaming.
- Confirmed each literal is used only as the `RawProvenance.source_path`
  synthetic CWD-anchored marker; identity is derived separately from
  `provider_transaction_id` (`split:{parent}:{index:04d}`,
  `merged:{split_group_id}`, `_provider_transaction_id(command, ...)`) and
  `source_sha256` (`sha256_hex(...)` / `_source_sha256(command, ...)`), neither
  of which reads `source_path`. The literal does not participate in any
  derived id or idempotency key.
- Renamed `.aeat-ledger-split` to `.cadrumo-ledger-split` and
  `.aeat-ledger-merge` to `.cadrumo-ledger-merge` in `_actions_split_merge.py`.
- Renamed `.aeat-manual-ledger` to `.cadrumo-manual-ledger` in
  `_actions_manual.py`.
- Swept the repo for other `aeat-ledger` / `manual-ledger` literal occurrences;
  the only other hits are unrelated `provider_name="manual-ledger"` string
  values in three test files, a distinct concept, out of scope for this Step.

## Outcome

Hard-cut rename landed with no compatibility bridge. Targeted split/merge/
manual-add/create ledger test suites (43 tests) pass; `ruff check` clean on
both touched files; `pytest --collect-only -q` on `src/cadrumo/application/ledger`
collects 374 tests cleanly. Committed at `23998bae11`.

## Notes

No idempotency-key or fingerprint dependency on the renamed literal was found
-- confirmed by reading both call sites' identity-deriving fields before
editing. No incidents.
