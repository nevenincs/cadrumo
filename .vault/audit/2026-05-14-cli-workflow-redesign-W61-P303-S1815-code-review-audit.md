---
tags:
  - '#audit'
  - '#cli-workflow-redesign'
date: '2026-05-14'
modified: '2026-05-14'
related:
  - '[[2026-05-13-cli-workflow-redesign-epic-plan]]'
  - '[[2026-05-13-cli-workflow-redesign-w61-p303-s1815-exec]]'
  - '[[2026-05-13-cli-workflow-redesign-manual-ledger-storage-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-ledger-transaction-management-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-app-ledger-ratios-shape-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-iva-prorrata-art-101-103-adr]]'
---



# `cli-workflow-redesign` W61.P303.S1815 Code Review

Status: PASS WITH MEDIUM FOLLOW-UPS. No CRITICAL or HIGH issues were found in the reviewed S1815 scope.

Review scope covered the W61.P303.S1815 plan row, exec record, the four listed ADRs, `src/aeat/domain/usage_ratios/__init__.py`, `src/aeat/domain/usage_ratios/_model.py`, `src/aeat/domain/usage_ratios/_service.py`, `src/aeat/application/ledger/_actions.py`, `src/aeat/application/ledger/_models.py`, and the focused usage-ratio and ledger tests.

W61.P303.S1815-001 | MEDIUM | Usage-ratio loader trusts the decrypted envelope without checking inner classification/version
`load_usage_ratios` asks `SecureObjectRepository.load` for `SensitivityClass.FINANCIAL` rows with schema version `1`, then parses `Envelope[UsageRatioProfile]` at `src/aeat/domain/usage_ratios/_service.py:53` and returns `envelope.payload` at `src/aeat/domain/usage_ratios/_service.py:64`. It does not recheck `envelope.classification` or `envelope.schema_version` after decrypting the inner payload. Adjacent secure repositories, including transaction catalogues and bucket event history, revalidate the inner envelope after parsing. The current storage path does not create plaintext fallback and the row metadata is still FINANCIAL, so this is not a data exposure issue. It is a secure-storage correctness gap: a restored, migrated, or corrupt secure object whose row metadata is acceptable but whose inner envelope claims another classification or future schema would be accepted instead of failing with `UsageRatioPersistenceError`.

W61.P303.S1815-002 | MEDIUM | `UsageRatioProfile` is not deeply immutable, so public callers can bypass validation after construction
`UsageRatioProfile` is declared frozen, but `ratios` is a mutable `dict` at `src/aeat/domain/usage_ratios/_model.py:81`. The docstring acknowledges that `frozen=True` does not freeze the inner mapping. Because `save_usage_ratios` accepts an already-constructed `UsageRatioProfile` and wraps it directly into an envelope at `src/aeat/domain/usage_ratios/_service.py:96`, a caller can mutate `profile.ratios` after validation and before save. That can persist a profile that would not pass normal constructor validation, or create a secure object that fails to reload later. The transaction catalogue already uses immutable mapping machinery for this kind of boundary, so the usage-ratio model should either freeze the mapping or revalidate/copy it at save time.

W61.P303.S1815-003 | LOW | Focused tests prove create-path no-write behavior but not update-path usage-ratio validation failures
The tests are real-behavior tests using SQLite secure objects and an ephemeral master key. They cover bucket-scoped usage-ratio persistence, encrypted database storage, configured category acceptance, alias rejection, category mismatch rejection, active-bucket missing entry rejection, `business_pct` drift rejection, manual ledger persistence, and create-path no catalogue/event writes on usage-ratio validation failures. The update path is statically ordered the same way: `update_manual_transaction` validates evidence and usage-ratio references before `_append_bucket_event` at `src/aeat/application/ledger/_actions.py:158` through `src/aeat/application/ledger/_actions.py:190`. The focused suite does not include an update-path usage-ratio validation failure asserting that the existing catalogue row and event history remain unchanged. This is a residual coverage gap, not an observed production defect.

Review notes:

- Bucket isolation is correct for the reviewed paths. Usage ratios are keyed as `profile:{bucket_id}` by `usage_ratios_object_key`, transaction repositories reject bucket mismatches, and ledger tests cover separate bucket catalogues and usage-ratio profiles.
- Secure storage uses `SecureObjectRepository` at FINANCIAL sensitivity for usage ratios and transaction catalogues. I found no plaintext fallback path in the reviewed production files.
- No CLI or business-logic leakage was introduced in the reviewed S1815 files. The new behavior is in domain/application services, not CLI command code.
- Alias/shim persistence is blocked for usage-ratio references: `validate_usage_ratio_reference` converts `usage_ratio_id` through `SpendingCategory`, requires it to match `category_id`, requires category eligibility, and tests reject alias-like keys.
- I found no usage-ratio/prorrata conflation. `usage_ratio_id` and `prorrata_reference` are distinct command, transaction, and raw fields; usage-ratio validation does not read or synthesize prorrata data.
- Event-before-save ordering is present: create and update append the bucket event before saving the transaction catalogue. Validation failures in the reviewed usage-ratio path occur before event append and transaction save.

Verification run during review:

- `uv run --no-sync pytest src/aeat/domain/usage_ratios/test_model.py src/aeat/domain/usage_ratios/test_service.py src/aeat/application/ledger/test_models.py src/aeat/application/ledger/test_actions.py -q` passed with 53 tests.

## Remediation Re-Review

Status: PASS WITH LOW FOLLOW-UP. No CRITICAL or HIGH issues were found in the W61.P303.S1815 remediation scope.

Reviewed the changed usage-ratio files, application ledger files, and S1815 exec record. Production code was not modified during this re-review.

Prior finding disposition:

- W61.P303.S1815-001: RESOLVED. `load_usage_ratios` now revalidates the decrypted inner envelope classification and refuses inner schema versions above the supported usage-ratio version before returning the payload. Focused service tests cover inner classification mismatch and future-version mismatch.
- W61.P303.S1815-002: RESOLVED. `UsageRatioProfile.ratios` is now exposed as a `Mapping`, canonicalized into a `MappingProxyType`, and serialized via a field serializer. The focused model test proves item assignment is rejected.
- W61.P303.S1815-003: MOSTLY RESOLVED. `update_manual_transaction` validates usage-ratio references before event append and catalogue save, and the focused test proves the catalogue row is unchanged after usage-ratio drift rejection. The event assertion should still be tightened to assert the bucket has exactly the original create event; as written, it checks the first event type and would not fail if an extra update event were appended. This is a LOW test-coverage gap only; the reviewed production ordering is correct.

W61.P303.S1815-RR-001 | LOW | Update-path no-event test should assert event count, not only first event type
`test_update_manual_transaction_rejects_usage_ratio_drift_without_event_or_save` verifies the catalogue remains unchanged and then asserts `event_repository.load().for_bucket("bucket-a")[0].event_type` is `LEDGER_TRANSACTION_CREATED`. That does not prove no later `LEDGER_TRANSACTION_UPDATED` event was appended. The production code validates usage-ratio references before `_append_bucket_event`, so no production defect was observed, but the regression test should assert the full event-type tuple remains exactly `(LEDGER_TRANSACTION_CREATED,)`.

Verification run during remediation re-review:

- `uv run --no-sync pytest src/aeat/domain/usage_ratios/test_model.py src/aeat/domain/usage_ratios/test_service.py src/aeat/application/ledger/test_models.py src/aeat/application/ledger/test_actions.py -q` passed with 57 tests.
