---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-W12-P26-S207]]'
---

# `secure-storage-production-hardening` `W12.P26.S207` Review

## S207-001 | PASS | Filing package init is manifest discovery, not storage runtime

`src/aeat/application/filing/__init__.py` builds and validates drafts from the
registry authority. Its manifest-bucket signal is registry/resource discovery:
`_resources().modelos.authority` and registry snapshot references. A source scan
found no direct file read/write, storage-path helper, settings load, naked
environment read, SQL route, secure-object repository construction, or runtime
repository factory call in the reviewed file.

## S207-002 | PASS | Re-exported filing operations do not execute on import

The module re-exports export, review, history, import, complementaria, and
runtime-profile helpers. Those imports expose the public filing API but do not
perform persistence or export writes at import time. Storage-bearing filing
modules remain owned by their own affected-file rows: `_history_repository.py`
by S208, `_review.py` by S209, `_runtime_repository.py` by S210, and
`runtime.py` by S212.

## S207-003 | TRACKED | Filing builder messages need a broader localization pass

The S207 scan found raw `ModeloBuilderError` and `ModeloCalculateError`
messages in `src/aeat/application/filing/__init__.py` and adjacent filing
runtime/calculation modules. They derive from the AEAT exception hierarchy, but
many do not yet carry `translated_message` keys. This is not a storage-routing
defect in S207, but it remains convention debt for the plan's W16 observation
pool and a later localized filing-error remediation slice. It is not marked
resolved by this row.

## S207-004 | PASS | Validation

- `uv run --no-sync ruff check src/aeat/application/filing/__init__.py src/aeat/application/filing/test_init.py src/aeat/application/filing/test_build_draft_identity.py src/aeat/application/filing/test_filing.py` passed.
- `uv run --no-sync pytest src/aeat/application/filing/test_init.py -q` passed with 9 tests.
- `uv run --no-sync pytest src/aeat/application/filing/test_build_draft_identity.py -q` passed with 1 test.
- `uv run --no-sync pytest src/aeat/application/filing/test_calculate.py -q` passed with 11 tests.
- `uv run --no-sync pytest src/aeat/application/filing/test_filing.py -q` passed with 20 tests after rerunning with a 300s timeout; the earlier combined command timed out and is not counted as pass evidence.

Reviewer note: no critical, high, medium, or low storage-routing findings remain
for the S207 slice. The raw filing error-message issue is tracked above as
broader convention debt, not closed.

Disposition: close `AFR-105` as `manifest-discovery`.
