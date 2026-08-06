---
tags:
  - '#audit'
  - '#ledger-latency-budget'
date: '2026-07-06'
modified: '2026-07-17'
body_hash: 'sha256:1f53c405de06ababcb266dbf788915cbdcff83493a35c49f81e27e75d735a91c'
related:
  - "[[2026-07-06-ledger-perf-optimization-plan]]"
  - "[[2026-07-05-ledger-latency-budget-adr]]"
  - "[[2026-07-06-ledger-perf-optimization-research]]"
---

# `ledger-latency-budget` audit: `S03 benchmark refresh review`

## Scope

Reviewed the S03 benchmark refresh in `src/aeat/application/aggregation/tests/test_ledger_scale_benchmark.py`.
The audit checked whether the new partition-read reporting used real repository behavior,
preserved the existing scale budget assertion, avoided fakes and monkeypatches, and produced
actionable output for the later batch-read and diagnostic-summary waves.

Reviewed the S04 repository-level guard in
`src/aeat/adapters/persistence/profile/tests/test_transactions_repository.py`. The audit
checked whether the new test uses the real SQL-backed runtime profile, mutates only the
derived date-index table to simulate staleness, and proves fallback parity against the
complete-index partition rather than mirroring repository logic.

Reviewed the S05 roundtrip guard in
`src/aeat/adapters/persistence/profile/tests/test_transactions_repository_roundtrip.py`.
The audit checked whether the test proves storage-level unchanged-row stability through
real secure-object revision metadata while changing one transaction row with the same
derived id.

Reviewed the S06 timestamp witness guard in
`src/aeat/adapters/persistence/profile/tests/test_transactions_repository_roundtrip.py`.
The audit checked whether the test exercises the real decoded-row witness helper and the
repository load boundary without monkeypatching JSON parsing or mutating production code.

Reviewed the S07 secure-object batch result contract in
`src/aeat/adapters/persistence/storage/sql/_secure_object_records.py`. The audit checked
whether the contract reuses the existing readable/unreadable failure model instead of
introducing a parallel diagnostics surface.

Reviewed the S08 secure-object batch implementation in
`src/aeat/adapters/persistence/storage/sql/secure_objects.py`. The audit checked whether
the implementation uses one targeted SQL `IN` query, preserves the fail-closed
`list_records` behavior, and shares the same row validation logic with namespace scans.

Reviewed the S09 secure-object batch tests in
`src/aeat/adapters/persistence/storage/sql/tests/test_secure_objects_part3.py`. The audit
checked whether the tests compare batch results to repeated real single loads, prove the
targeted SQL query shape, and cover mixed readable/schema-drift behavior without mocks.

Reviewed the S10 transaction date-range adoption in
`src/aeat/adapters/persistence/profile/transactions.py`. The audit checked whether the
indexed `load_for_date_range` path now uses the targeted secure-object batch primitive
without changing the stale-index full-scan fallback, missing-row omission, or domain
schema-drift wrapping.

Reviewed the S11 transaction partition adoption in
`src/aeat/adapters/persistence/profile/transactions.py`. The audit checked whether
`partition_by_date_range` now uses the targeted secure-object batch primitive only after
the existing completeness gate succeeds, while preserving the stale-index full-scan
fallback and plaintext out-of-window stub construction.

Reviewed the S12 repository-level batch-read proof in
`src/aeat/adapters/persistence/profile/tests/test_transaction_date_index.py`. The audit
checked whether the test observes real SQL emitted by the SQL-backed repository, proves a
single targeted secure-object batch read for the in-window rows, and still asserts the
expected in-window and out-of-window partition sets.

Reviewed the S17 domain summary model in `src/aeat/domain/transactions/_models.py` and
`src/aeat/domain/transactions/__init__.py`. The audit checked whether the new summary
payload is additive, carries only the ADR-authorized count and filing-date span, avoids
decrypted financial fields, and is exported through the public transaction facade.

Reviewed the S18 repository protocol documentation in
`src/aeat/domain/transactions/_protocols.py`. The audit checked whether the
`partition_by_date_range` contract now permits the compact summary representation while
retaining the same in-window parity, no-silent-drop, and plaintext-only constraints.

Reviewed the S19 repository summary emission in
`src/aeat/adapters/persistence/profile/transactions.py` and
`src/aeat/adapters/persistence/profile/tests/test_transaction_date_index.py`. The audit
checked whether both indexed and stale-index fallback partitions populate the compact
summary, whether the summary carries only count and filing-date span, and whether
existing row-level behavior remains compatible during the consumer migration.

Reviewed the S20 source-diagnostic summary surface in
`src/aeat/application/aggregation/_source_mesh.py` and
`src/aeat/application/aggregation/tests/test_source_mesh.py`. The audit checked whether
the new diagnostic fields remain optional, require a complete count/date-span tuple when
used, reject reversed spans, and expose a reusable helper for resolver conversion.

## Findings

No critical, high, medium, or low issues were found in the S03 benchmark refresh.

No critical, high, medium, or low issues were found in the S04 repository-level fallback
parity guard.

No critical, high, medium, or low issues were found in the S05 unchanged-row save
reconciliation guard.

No critical, high, medium, or low issues were found in the S06 timestamp witness guard.

No critical, high, medium, or low issues were found in the S07 batch-load outcome alias.

No critical, high, medium, or low issues were found in the S08 targeted batch read
implementation.

No critical, high, medium, or low issues were found in the S09 batch-load parity tests.

No critical, high, medium, or low issues were found in the S10 date-range batch-read
adoption.

No critical, high, medium, or low issues were found in the S11 partition batch-read
adoption.

No critical, high, medium, or low issues were found in the S12 partition batch-read proof.

No critical, high, medium, or low issues were found in the S17 domain summary model.

No critical, high, medium, or low issues were found in the S18 repository protocol
documentation update.

No critical, high, medium, or low issues were found in the S19 repository summary
emission.

No critical, high, medium, or low issues were found in the S20 source-diagnostic summary
surface.

No critical, high, medium, or low issues were found in the S21 IVA repository-backed
summary emission.

No critical, high, medium, or low issues were found in the S22 M130/M100 income
repository-backed summary emission.

No critical, high, medium, or low issues were found in the S23 M130 gasto
repository-backed summary emission.

No critical, high, medium, or low issues were found in the S24 impatriado income
repository-backed summary emission.

No critical, high, medium, or low issues were found in the S25 source-mesh summary
diagnostic mapping.

No critical, high, medium, or low issues were found in the S26 IVA summary
regression tests.

No critical, high, medium, or low issues were found in the S27 M130/M100 income
summary regression tests.

No critical, high, medium, or low issues were found in the S28 M130 gasto summary
regression tests.

No critical, high, medium, or low issues were found in the S29 impatriado summary
regression tests.

No critical, high, medium, or low issues were found in the S30 source-mesh summary
regression test.

No critical, high, medium, or low issues were found in the S31 transaction id
after-validator rewrite.

No critical, high, medium, or low issues were found in the S32 transaction coercion
helper removal.

No critical, high, medium, or low issues were found in the S33 transaction service
construction-path check.

No critical, high, medium, or low issues were found in the S34 transaction JSON
roundtrip regression test.

No critical, high, medium, or low issues were found in the S35 tampered transaction id
JSON regression test.

No critical, high, medium, or low issues were found in the S36 encrypted repository
JSON-mode validator regression test.

## Recommendations

Keep the current S03 benchmark shape. The file-level ruff check passed, and the two
changed integration benchmark nodes passed with real adapter output:
`iva_quarterly_partitioned` reported `partition_reads=20`,
`partition_in_window_rows=15000`, and a paired full-scan delta; `modelo_calculate_diagnostic`
reported `partition_reads=4` and `partition_in_window_rows=7484`.

Keep the current S04 test shape. The file-level ruff check passed, and the focused unit
test `test_partition_fallback_matches_complete_index_partition` passed.

Keep the current S05 test shape. The file-level ruff check passed, and the focused unit
test `test_transaction_catalogue_save_skips_unchanged_secure_object_rows` passed.

Keep the current S06 test shape. The file-level ruff check passed, and the focused unit
test `test_transaction_timestamp_witness_rejects_missing_modified_at_from_decoded_row`
passed.

Keep the current S07 contract shape. The records-module ruff check passed.

Keep the current S08 implementation shape. The storage-module ruff check passed, and the
existing readable/unreadable listing tests passed after the shared conversion refactor.

Keep the current S09 test shape. The file-level ruff check passed, and the two focused
batch-load tests passed.

Keep the current S10 helper shape. The transaction repository ruff check passed, and the
three focused `load_for_date_range` date-index tests passed against the real SQL-backed
repository path.

Keep the current S11 partition adoption. The transaction repository ruff check passed, and
the three focused partition date-index tests plus the repository stale-index parity test
passed against the real SQL-backed repository path.

Keep the current S12 test shape. The date-index test ruff check passed, the new focused
batch-read proof passed, and the neighboring partition tests passed against the real
SQL-backed repository path.

Keep the current S17 additive model shape. Domain ruff checks passed after import-order
fixing, and a direct public-facade import/validation check passed for
`OutOfWindowTransactionSummary`.

Keep the current S18 protocol wording. Domain ruff checks passed, and direct
`LedgerDatePartition` construction with the optional summary field omitted passed.

Keep the current S19 additive emission shape until S20-S25 migrate consumers to the
summary field. Ruff passed for the touched repository/domain files, and the four focused
partition tests passed.

Keep the current S20 source-mesh helper shape. Ruff passed for the source-mesh files, and
the full `test_source_mesh.py` unit file passed with the new summary validation coverage.

Keep the current S21 IVA result shape. The repository-backed path now carries the compact
summary without allocating row-level out-of-window issues, while the full-catalogue
aggregation path still emits row-level `OUTSIDE_PERIOD` issues. Ruff passed for
`_iva_ledger.py`, a real repository-backed smoke probe passed, and the focused
full-catalogue caja-basis outside-period test passed.

Keep the current S22 income result shape. Both repository-backed income entry points now
carry the compact summary without allocating row-level out-of-window issues, while pure
full-catalogue aggregation still emits row-level `OUTSIDE_PERIOD` issues. Ruff passed for
`_renta_income_ledger.py`, real M130 and M100 repository-backed smoke probes passed, and
the focused pure M130 cumulative-window test passed.

Keep the current S23 gasto result shape. The repository-backed gasto entry point now
carries the compact summary without allocating row-level out-of-window issues, while pure
full-catalogue aggregation still emits row-level `OUTSIDE_PERIOD` issues. Ruff passed for
`_renta_gasto_ledger.py`, a real repository-backed smoke probe passed, and the focused
pure Q1 gasto cumulative-window test passed.

Keep the current S24 impatriado result shape. The repository-backed impatriado entry point
now carries the compact summary without allocating row-level out-of-window issues, while
pure full-catalogue aggregation still emits row-level `OUTSIDE_PERIOD` issues. Ruff passed
for `_impatriado_income_ledger.py`, a real repository-backed smoke probe passed, and the
focused pure ES-source aggregation test passed.

Keep the current S25 source-mesh helper shape. The converted resolvers now prepend one
structured source diagnostic for each compact out-of-window summary without altering
binding values, provenance, or source transaction ids. Ruff passed for `_modelo_bindings.py`,
the direct helper probe passed, and an ordinary IVA source-mesh resolver test passed.

Keep the current S26 IVA test expectations. The repository-backed tests now assert the
compact summary count/date span and zero row-level out-of-window issues, while pure
full-catalogue assertions still cover row-level `OUTSIDE_PERIOD` behavior. Ruff passed for
`test_iva_ledger.py`, and the three updated repository-backed tests passed.

Keep the current S27 income test expectations. The repository-backed M130 and M100 tests
now assert compact summary count/date spans and zero row-level out-of-window issues, while
pure full-catalogue assertions still cover row-level `OUTSIDE_PERIOD` behavior. Ruff passed
for both income test files, and the five updated repository-backed tests passed.

Keep the current S28 gasto test expectations. The repository-backed gasto tests now assert
compact summary count/date spans and zero row-level out-of-window issues, while pure
full-catalogue assertions still cover row-level `OUTSIDE_PERIOD` behavior. Ruff passed for
`test_renta_gasto_aggregation.py`, and the three updated repository-backed tests passed.

Keep the current S29 impatriado test expectations. The repository-backed impatriado tests
now assert compact summary count/date spans and zero row-level out-of-window issues, while
pure full-catalogue assertions still cover row-level period and source-scope reasons. Ruff
passed for `test_impatriado_income_ledger.py`, and the three updated repository-backed
tests passed.

Keep the current S30 source-mesh expectation. The IVA resolver test now asserts one
structured out-of-window source diagnostic with count and filing-date span while preserving
the raw full-catalogue row-level assertion. Ruff passed for `test_modelo_source_mesh_ledger.py`,
and the updated resolver test passed.

Keep the current S31 transaction id validator shape. The missing-id default now derives
from already validated `raw`, and explicit id tampering is rejected by an after-validator.
Ruff passed for `_models.py`, focused model tests passed, the direct tamper probe passed,
and the encrypted repository roundtrip smoke test passed. Obsolete manual coercion helpers
remain intentionally for S32 removal.

Keep the current S32 cleanup. The transaction-specific manual coercion helpers and unused
`ValidationError` import are gone, while shared helper functions remain. Ruff passed for
`_models.py`, focused domain model tests passed, the encrypted repository roundtrip smoke
test passed, and `rg` confirmed the removed helper names are absent.

Keep `_service.py` unchanged for S33. Service update paths already carry explicit ids from
`transaction.model_dump(mode="python")`, and missing-id construction is preserved by the
model-level default factory. Ruff passed for `_service.py`, the direct missing-id probe
passed, and focused catalogue service tests passed.

Keep the current S34 test. It builds a non-default transaction without an explicit id,
asserts the derived id from the input raw row, roundtrips through JSON mode, and asserts
representative non-default fields. Ruff passed for `test_models.py`, and the new focused
test passed.

Keep the current S35 test. It mutates only `transaction_id` in a serialized
storage-shaped JSON payload and asserts the after-validator rejects the mismatch. Ruff
passed for `test_models.py`, and the new focused tamper test passed.

Keep the current S36 repository test. It persists a transaction built without an explicit
id, verifies the encrypted row carries storage-shaped JSON strings, then loads through the
repository and reasserts equality plus the derived id. Ruff passed for
`test_transactions_repository_roundtrip.py`, and the new focused repository test passed.

Keep the current S37 catalogue JSON-mode fix. The full transaction-domain suite exposed
two catalogue roundtrip regressions after the validator rewrite; the fix routes
JSON-shaped nested catalogue payloads through JSON-mode `Transaction` validation while
leaving ordinary Python-mode construction unchanged. Ruff passed for the touched
transaction files, the two focused catalogue regressions passed, and the full
`src/aeat/domain/transactions/tests` suite passed with 108 tests.

Keep the current S38 test repair. The repository suite exposed one stale fixture that
changed a transaction's raw filing date through unchecked `model_copy` while retaining
the old content-derived id. The test now rebuilds the moved row through
`Transaction.model_validate` without an explicit id, matching the content-addressed edit
contract. Ruff passed for `test_transaction_date_index.py`, the focused regression test
passed, and the full profile persistence suite passed with 104 tests.

Keep the current S39 measurement record. The selected 30k-row integration benchmark
passed after the validator rewrite and the reference now records the S13-to-S39 deltas:
full ledger read P95 `5.126s`, annual renta P95 `5.751s`, and M130 calculate P95
`1.141s` with unchanged `partition_reads=4` and `partition_in_window_rows=7484`.

Keep the current S40 write-path benchmark. It adds a real encrypted-SQLite 30k-row
single-transaction save diagnostic, restores the original seeded catalogue after timing,
and reports the named residual components separately. Ruff passed for the benchmark file,
and the focused integration node passed with save P95 `2.659s`, serialize+hash P95
`1.399s`, and namespace hash scan P95 `0.201s`.

Keep the current S41 attribution. The reference now records that serialize+hash dominates
namespace hash scanning for the single-row mutation residual: P95 `1.399s` versus
`0.201s`, against a real one-row save P95 of `2.659s`. The follow-up design should focus
on avoiding all-row envelope serialization and payload hashing while preserving the
existing unchanged-row skip and atomic batch contracts.

Keep the current S42 research. It treats dirty-set writes as a separate decision surface,
not as part of the accepted read-path ADR, and recommends an additive repository API that
serializes only known changed/new transactions while keeping the full reconciliation
fallback, membership-index bucket isolation, derived date-index repairability, unchanged
row revision stability, and secure-object co-write atomicity.

Keep the current S43 proposed ADR. It captures dirty-set save semantics as an additive,
approval-gated repository write contract and explicitly keeps full reconciliation as the
fallback. Frontmatter, placeholders, and body-link checks passed; repository-wide
modified-stamp, legacy ADR-status, and older schema warnings remain unrelated.

Keep the current S44 registry-cache confirmation. `ValidatedRegistryAuthority.load` is
already keyed by registry and source-evidence fingerprints behind `_load_authority`'s
process cache, and `test_authority.py` covers repeated cache hits plus invalidation for
fragmented registry revisions and source evidence changes. The focused authority suite
passed with 10 tests, so no registry runtime change is justified in this optimization
slice.

Keep the current S45 secure-object batch-read confirmation. `load_many` issues one
targeted secure-object `IN` query, and the transaction partition test proves a complete
date index reads in-window encrypted rows through one batch select while using only one
point lookup for the membership index. The storage part-3 suite and focused partition
test passed, so no additional session or HKDF caching change is needed for this slice.

Keep the current S46 feature-surface result. Ruff passed across the 22 owned Python
files, and the scoped pytest modules passed with 184 tests and 6 integration benchmark
nodes deselected by normal marker policy. Feature-owned vault checks are clean after
the ADR research relation and documentation hygiene fixes; the remaining `vault check
all --feature ledger-latency-budget` nonzero exit is caused only by 29 pre-existing
global feature-rename-integrity errors in older exec folders outside this feature.

No critical, high, medium, or low issues were found in the final code-review pass over
the completed feature surface. The review rechecked the batch secure-object read, the
transaction partition adoption, the summary diagnostic path, the transaction validator
rewrite, and the benchmark additions against the accepted ADR and plan constraints.

Keep the completed implementation as scoped. The only review caveat is intentional:
Python-mode `Transaction.model_validate` now expects typed enum/date inputs unless a
payload is routed through JSON-mode validation; production construction paths reviewed
use typed command/domain values, and storage/catalogue JSON roundtrips are covered by
the new JSON-mode tests.
