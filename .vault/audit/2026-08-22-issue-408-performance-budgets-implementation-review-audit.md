---
tags:
  - '#audit'
  - '#issue-408-performance-budgets'
date: '2026-08-22'
modified: '2026-08-22'
body_schema: 'body-v1'
body_hash: 'sha256:83e86e9f5d52f804bef3921a993bc0431b6a0860456e812364fed56887528e02'
related: []
---



# `issue-408-performance-budgets` audit: `Scale performance budget implementation review`

## Scope

Fresh-context review of implementation commit
`d0fa1c46d38816477f4add16a19f0ef204bf1c83` against its parent and current
branch HEAD. The audit covered secure exact-ID transaction reads, SQL namespace scope,
memoization identity and staleness, validated-registry authority injection, revision-carry
parity, compact excluded-row summaries, repository protocol compatibility, and the real
30,000-row performance gates. It also compared benchmark constants and fixtures against
the parent to confirm the strict `< 3.0` CPU-second ceilings, transaction volume, filing
years, and sample axes were not weakened. Production code was not modified.

## Findings

### targeted-row-version-gate | high | Exact-ID reads bypass the transaction schema cutover refusal

`TransactionCatalogueRepository.load_by_ids` delegates directly to
`_load_transactions_by_ids`, whose `load_many` call supplies only a maximum supported
version. Unlike `load`, it does not run `_require_current_rows` and does not atomically
migrate the addressed rows. Consequently a legacy transaction row at a supported older
version can be decrypted and returned by the new exact-ID path even though the ordinary
catalogue read explicitly refuses until the IVA-authority cutover has persisted current
rows. The optimized `_draft_ledger_anchor` now uses this path for filing-snapshot
fingerprints, so the performance change creates a calculation/persistence route around a
load-bearing migration boundary. The new exact-ID regression covers current rows, missing
ids, duplication, and addressed identity, but contains no legacy-version refusal or
parity check against `load`'s version behavior.

### memoized-write-staleness | medium | Delegated saves leave every memoized read view stale

`MemoizedTransactionCatalogueRepository` implements the full
`TransactionCatalogueRepositoryProtocol`, including `save`, but `save` only delegates to
the wrapped repository. It does not clear or replace `_catalogue`, `_date_range_catalogues`,
`_partition_catalogues`, or `_id_catalogues`. A caller that reads, saves through the same
protocol object, and reads again receives pre-save transactions, partitions, and targeted
fingerprints even though the authority repository has committed the replacement. Existing
tests intentionally demonstrate snapshot behavior when another repository instance writes,
but the save-delegation test never primes a cache before calling `memoized.save`, so it does
not cover the wrapper's own read-after-write contract. Current calculation wiring treats
the wrapper as read-only in practice, which limits immediate reach, but the public protocol
shape advertises write compatibility and makes the stale behavior available to any typed
consumer.

No critical findings were identified. Exact transaction keys remain bucket-qualified,
secure reads remain namespace-scoped and enforce addressed payload identity, and the new
raw-row namespace filter is parameterized in SQL. The compact out-of-window summary
preserves the complete excluded count and filing-date span when row projections are
suppressed above 1,024 entries, while small-ledger and full-scan fallback compatibility is
retained. Applicability and carry resolution now reuse `ValidatedRegistryAuthority`, and
focused parity gates remained green. Protocol additions match the concrete transaction and
work-unit repositories used by production callers.

The benchmark contract was not weakened: `_P95_BUDGET_CPU_SECONDS` remains `3.0` and both
budget assertions remain strict `<`; the anti-vacuity controls remain strict `>`; the
fixture remains 30,000 transactions across ten filing years; quarterly sampling remains
20 iterations; and the M130 diagnostic still covers its four quarters. The full real
encrypted-SQLite benchmark completed with all seven cases passing, including both degraded
full-scan controls.

### corrective-query-budget-regression | high | Security-preserving addressed batches exceed both strict performance budgets

Corrective commit `cf5196b7118a87d9b3a026ec868955079a44c324` replaces each targeted
payload read with three addressed secure-object batches: current-schema inspection,
atomic-migration version inspection, and payload loading. This correctly avoids a namespace
scan and closes `targeted-row-version-gate`, but the sequential 30,000-row benchmark now
fails both affected strict gates. Quarterly partitioned aggregation measured a 3.453
CPU-second P95 over the unchanged 20 samples, and M130 calculation measured 4.391 CPU
seconds over its unchanged four-quarter sample, both above the unchanged `< 3.0` ceiling.
The degraded controls remained strongly non-vacuous: full scans measured approximately
16.8 to 22.4 CPU seconds. One selected anti-control passed and both optimized-path budget
tests failed. The performance objective therefore no longer holds at the corrective HEAD;
security parity cannot be traded for a budget violation.

## Recommendations

- For `targeted-row-version-gate`, make exact-ID reads enforce the same current-version
  contract as ordinary reads before returning any transaction. Add a real encrypted-store
  regression with a legacy addressed row proving both `load` and `load_by_ids` refuse (or
  migrate, if the owning cutover contract is deliberately changed) identically.
- For `memoized-write-staleness`, either make the wrapper explicitly read-only through a
  narrower protocol, or invalidate/reseed every affected cache after a successful delegated
  save. Add read-save-read coverage for full, date-window, partition, and exact-ID views.
- Do not integrate the commit or close issue 408 until both findings are resolved and the
  focused correctness and full benchmark gates remain green.

## Resolution verification

Corrective commit `cf5196b7118a87d9b3a026ec868955079a44c324` resolves the two
original settled findings. Exact-ID reads now apply the same current-row refusal before
using `migrate_many_atomically`; a real v1 fixture proves both full and targeted reads raise
the same `LedgerStorageError`, leave all rows at v1, and read successfully only after the
explicit authority migration moves the complete transaction namespace to v2. The schema
guard, migration inspection, and payload read are all exact `object_key IN (...)` queries,
with an explicit regression proving no secure-object namespace scan. Generic migration
loads are batched by namespace/class/version contract while still passing records through
the existing `_record_from_row` classification, version, envelope, and integrity exception
funnel and the existing cross-namespace CAS conflict proof.

The memoized wrapper now clears its full-catalogue, date-window, partition, and exact-ID
caches only after a successful delegated save. Its regression primes all four views,
replaces the catalogue through the wrapper, observes the replacement through every view,
and proves the removed transaction id no longer resolves. Focused migration, exact-read,
secure-storage, and cache tests passed: 48 tests.

The benchmark constants, fixture volume, and iterations remain unmodified, but the new
`corrective-query-budget-regression` finding keeps the implementation blocked. Issue 408 is
not safe to integrate or close until the exact security semantics and strict performance
budgets are simultaneously green.
