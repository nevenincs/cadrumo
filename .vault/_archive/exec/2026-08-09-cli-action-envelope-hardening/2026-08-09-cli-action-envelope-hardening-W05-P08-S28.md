---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:33f8548f0511a591efb221d8570809cc6dc8fb1555ee70ded074b2ef5efdba58'
step_id: 'S28'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---
# Delete ErrorCode.default_suggestion and define only the current catalogue-backed error action or explicit no-recovery projection

## Scope

- `src/cadrumo/core/errors/_registry.py`
- `dev/error_code_default_suggestion_preimage_ledger.py`
- `dev/error_code_default_suggestion_preimage.json`
- `src/cadrumo/core/errors/tests/test_registry.py`
- `src/cadrumo/core/errors/tests/test_envelope.py`
- `src/cadrumo/entrypoints/cli/tests/test_error_registry_contract.py`

## Description

- Reconciled the prior deletion commit `7f40a9388e897574e18aa50d674403152cb4cc83` against its immutable parent `930ef9f4017a23cccaf4990d287beb014fc9723c` after independent review found that the deletion had removed source authority without retaining a durable identity ledger.
- Kept `ErrorCode` policy-free: it has no `default_suggestion`, action, or no-recovery authority; envelope actions remain supplied only as resolved typed precondition actions.
- Replaced the core error-category text-prefix fallback with registered locale keys and added the complete seven-category prefix family for `en`, `es`, `ca`, and `hu`.
- Added `dev/error_code_default_suggestion_preimage.json` and its AST-backed parser/gate. The ledger contains all 612 former declarations, retaining the full source commit, code, qualname, shard, exact old expression source, source locator, and the sole downstream owner `S50` through `S57` or `S64`.
- Added direct real-source tests that reject missing, extra, duplicate, and wrong-owner historical rows, preserve repeated `None` rows by source location, and assert that the live model cannot regain retired policy fields.
- Updated the accepted campaign reference through `vaultspec-core vault set-body`, after a dry run and expected-blob-hash guard, to identify this dedicated historical ledger without contaminating the current candidate-disposition census.

## Outcome

- The historical-ledger CLI gate reads every pinned shard with `git show`, AST-extracts the full preimage, and passes only on exact ordered source-multiset equality; it reported 612 unique source identities over the nine required shards and owners.
- The seven error categories render from their selected locale catalogue across all four supported output languages; focused CLI contract coverage exercised the 7 x 4 matrix without hard-coded English output assertions.
- Focused S28 and historical-ledger coverage reported 29 passed in the configured unit lane. Targeted Ruff format and lint passed, BasedPyright reported 0 errors and 0 warnings, and scoped diff whitespace checking passed.
- Independent review disposition: PASS after the historical-ledger remediation; the earlier HIGH finding is closed by the strict non-runtime ledger and exact gate.

## Notes

- `dev.locales scaffold --check` remains outside this Step's green boundary because the concurrent Modelo 111 registry work currently rejects four export-header keys: `presenter_nif`, `page_complementaria`, `colegio_concertado`, and `aeat_seal`. The error occurs before locale parity and is not masked or worked around here.
- The checked-in current disposition ledger intentionally remains current-only. It rejects stale candidates, so the historical preimage is deliberately stored in the dedicated non-runtime ledger rather than as compatibility rows.
