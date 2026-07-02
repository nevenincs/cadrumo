---
tags:
  - '#exec'
  - '#arch-remediation-gates-ratchet'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S12'
related:
  - '[[2026-07-02-arch-remediation-gates-ratchet-plan]]'
---

# Confirm ledger gates and lint-imports together

## Scope

- `.importlinter`
- `src/aeat/tests/test_importlinter_ledger.py`

## Description

- Ran the focused ledger ratchet tests.
- Ran Import Linter after the ratchet test file was present.
- Ran `pytest --collect-only -q` with full output written to a log file before slicing the tail.

## Outcome

`uv run --no-sync pytest src/aeat/tests/test_importlinter_ledger.py -q` passed with 3 tests. `uv run --no-sync lint-imports` passed with 4 contracts kept. `uv run --no-sync pytest --collect-only -q` completed cleanly.

## Notes

Full collect-only output was written to `%TEMP%\\aeat-gates-ratchet-collect-only.log`.
`vaultspec-core vault check all` was run during review and failed on pre-existing
repo-wide vault drift: unrelated template placeholders, feature-folder rename
drift, schema/ADR-status drift, and unrelated feature metadata warnings. Scoped
inventory from that run: this plan intentionally has no same-feature ADR because
it is governed by the program ADR, and the generated feature index was already
stale relative to the newly created exec/audit records. Those vault issues were
recorded and left untouched.

An earlier pre-commit `pytest --collect-only -q` attempt failed with 46
unrelated collection errors rooted in
`aeat.adapters.outbound.storage._errors.OutboundStoragePathTooLongError` missing
an ErrorCode registry entry while outbound storage, Google, and CLI files
carried non-plan WIP in the shared worktree. The gate was rerun after that peer
state settled and passed.

Later pre-commit `lint-imports` reruns surfaced additional live worktree imports
in `src/aeat/core/tests/test_paths.py` and
`src/aeat/application/bucket_maintenance/tests/test_service_import_export.py`.
The core-test imports had landed in `HEAD`, and the bucket-maintenance test
import is part of the shared structural worktree flow, so those edges were
added to the ledger baseline before the final gate run.
