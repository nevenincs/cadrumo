---
tags:
  - '#audit'
  - '#issue-408-performance-budgets'
date: '2026-08-22'
modified: '2026-08-22'
body_schema: 'body-v1'
body_hash: 'sha256:a6dbc72c9e0d8fae2739e8b301221a57f0cf89590a49e7b090ce11cd7225d167'
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
