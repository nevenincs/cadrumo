---
tags:
  - '#reference'
  - '#ledger-latency-budget'
date: '2026-07-06'
modified: '2026-07-17'
body_hash: 'sha256:322388764ca2f46d6e567e22cff3638398905f75a1bc133d847b6c1d88b0c6f4'
related:
  - "[[2026-07-05-ledger-latency-budget-adr]]"
---

# `ledger-latency-budget` reference: `Performance optimization surfaces - Fable discovery pass 1`

Rolling catalogue of performance-optimization surfaces across the ledger,
secure-storage, registry, and calculation paths. Discovered by a Fable optimization-guru
deep-analysis pass (2026-07-06) grounded in the `2026-07-05-ledger-latency-budget` cost
model. Each surface names concrete `file:function` anchors, an estimated impact, an
effort/risk class, and whether it is a safe autonomous win or needs an ADR / operator
ruling. Fable is the standing guru and appends new surfaces on each sweep.

## Summary

### Load-bearing cost model (measured, from the ADR)

A full-scan of 30k encrypted rows costs ~7s P95; AES-256-GCM decryption is only ~0.5s of
that. The dominant cost is per-row pydantic validation plus content-hash identity
re-derivation. After #408 Path A: IVA quarterly aggregation P95 1.9s (meets the 3.0s
budget); M130 modelo-calculate 4.7s (over); unfiltered ledger listing read ~7s;
`_renta_ledger` annual ~7s (excluded from the partition pending #599). Levers win by
shrinking rows-decrypted-and-validated (done for period reads) OR by cutting the per-row
constant (the remaining frontier).

### Tier 1 - safe autonomous wins (no semantic change, no ADR)

- S1a double-parse: `transactions.py` `load` `json.loads` every row for the D6 timestamp
  witness, then pydantic `model_validate_json` re-parses the same bytes. Every row parsed
  twice. Fix: a persisted-boundary envelope with REQUIRED `created_at`/`modified_at` (no
  `default_factory`) so the guard is structural and one parse suffices; keep the
  anti-tautology roundtrip proof. Est. 20-35% off every full scan.
- S1b N+1 partition read: `partition_by_date_range` loads each in-window row via an
  individual `SecureObjectRepository.load` (fresh sessionmaker + BEGIN/COMMIT + HKDF +
  fetch + decrypt). A Q4 window ~3,000 rows = ~3,000 SQL transactions per calculate. Fix:
  a batched `WHERE namespace=? AND object_key IN (:digests)` read (the streaming
  `iter_records_with_failures` shape already exists). Est. 1-2s off M130; biggest
  period-read lever. Same fix for the caller-less `load_for_date_range`.
- S1c key/session churn: `HashedLookup.compute` (`_encrypted_columns.py`) re-runs HKDF on
  every digest (30k per scan, again per bind); `session_scope` (`session.py`) builds a new
  sessionmaker per call. Fix: cache the derived lookup subkey on the bucket session
  (evicted at seal); cache sessionmaker per engine. Est. 100-300ms/scan + relief for S1b.
- S1d per-calculate re-parse: `_load_index_ids` (`transactions.py`) re-parses the
  encrypted membership-index envelope into a `set[str]` on every call from `partition_by_
  date_range`/`load_for_date_range`/`load`/`exists` — one parse per DISTINCT window
  requested in a calculate (e.g. an IVA quarterly window plus a separate M130
  cumulative-annual window), not per call. Corrected after implementation: the envelope
  parse does NOT `sorted()` 30k rows (that claim was wrong; `sorted()` only runs over the
  small selected/in-window subset per the O2/batch-read work, and at membership-serialize
  time on save); `exists()` has zero live callers in the calculate resolver mesh today, so
  its "full parse for a bool" cost is theoretical, not measured. Attempted fix (instance-
  level memoization of the parsed set, invalidated on this instance's own writes) was
  BUILT, TESTED, AND REVERTED: it broke a real ledger test
  (`test_finalized_modelo_reference_blocks_lifecycle_removal_prior_id_and_reset`) because
  multiple independent `TransactionCatalogueRepository` instances legitimately write to
  the SAME bucket in one command flow (e.g. several `_create_manual_row` calls each
  construct a fresh repository instance) — an instance's own-write invalidation cannot see
  a SIBLING instance's write, so a reused first instance served a stale membership set and
  silently dropped newly-added rows on its next `load()`. A safe fix needs either a
  storage-level invalidation signal shared across instances or scoping the cache
  explicitly to a caller that can PROVE single-instance exclusivity for its lifetime (e.g.
  the calculate `_MemoizedTransactionCatalogueRepository` wrapper, which owns its
  underlying repository exclusively and never calls `save`) — not the general-purpose
  concrete repository every ledger command constructs fresh-and-reused-with-siblings.
  Residual accepted as small (one extra set-parse per distinct window, not per call; see
  the S1b analysis for the measured cost class).
- S1e registry TTL: every `ValidatedRegistryAuthority.load` after the 1s TTL re-stat-walks
  the whole fragmented registry tree (M100 = thousands of fragments) to build the cache
  key. The bundled read-only tree cannot change under a running process. Fix: a longer TTL
  for the bundled tree. Est. 100s of ms/calculate on Windows.

### Tier 2 - high value, small ADR / operator ruling

- S2a out-of-window diagnostic flood: each partition returns ~27k
  `OutOfWindowTransactionStub`s; each aggregator builds one `LedgerIssue` per stub; each
  resolver wraps each into a `CalculationSourceDiagnostic`. M130 runs income AND gasto =
  ~135k pydantic constructions per calculate, pure diagnostics work for rows that cannot
  touch a casilla. Est. 1-2s + heavy GC. Fix: an aggregated OUTSIDE_PERIOD summary
  diagnostic (count + date-span + optional plain id tuple). The Path-A ADR anticipated
  "summary counting" - SMALL ADR AMENDMENT, risk confined to the diagnostics channel.
- S2b write-path full serialization (largest UNTRACKED cost): `_reconcile` serializes ALL
  30k rows + SHA-256s each on EVERY single-row `ledger add/update/classify` (to discover
  29,999 unchanged) + re-reads 30k index rows + re-parses the 30k-id membership index.
  Multi-second per one-row mutation at scale; absent from the ADR and all residuals. Fix:
  an application-layer dirty-set (the mutation knows the changed id) or a
  `(transaction_id, modified_at)`-keyed bytes/hash cache (envelope bytes are
  deterministic). No confidentiality dimension; diff-write is a contract -> design
  note / mini-ADR + roundtrip parity. Top nomination for a new tracked issue.
- S2c Transaction before-validator (#607 O5 lever): `_enforce_derived_transaction_id`
  (`_models.py`) intercepts before pydantic-core's Rust path and per row runs a full slow
  `RawTransaction.model_validate`, a SHA-256 `derive_transaction_id`, and five hand-rolled
  coercion sweeps re-implementing native JSON-mode. Fix: validate `raw` through the JSON
  path, move the id check to `mode=after`. Est. 30-50% off validation. Roundtrip-gated.

### Tier 3 - ADR-gated, only if the budget still fails after Tiers 1-2

- S3a trusted-read skip / payload-hash amortization of the per-read id re-derivation
  (integrity control; AES-GCM AAD already authenticates post-decrypt bytes). ADR.
- S3b process-level payload-hash-keyed catalogue cache (validity via the decryption-free
  `namespace_payload_hashes` scan) - extends plaintext-in-memory lifetime; low production
  value while the CLI is process-per-command. Operator ruling.
- S3c msgspec mirror decode (parallel schema, drift risk) + parallel decrypt/validate
  (validation is GIL-bound; process pools raise confidentiality questions). Last resort.
- S3d lazy per-modelo registry validation (`_load_authority` runs full-tree
  `validate_registry`; the per-modelo path is dead code). Cross-modelo relation-gate care.
  ADR.
- S3e #599 effective-filing-date index key (invoice-issue-date preferring) - touches the
  five-column schema-lock the ADR just re-affirmed; likely an ADR superseding the index
  contract. Operator-reserved.

### Cross-cutting

Memory/GC: a full `load` materializes 30k `Transaction` graphs (hundreds of MB) plus
S2a's 135k diagnostic objects; the listing-read pagination lever should be windowed
end-to-end, not load-then-slice. Every lever preserves regulated-gate order, declared tax
values, and the plaintext index schema unless flagged Tier 3 / operator-reserved. Fable's
headline: S1b (batch read) + S2a (diagnostic summary) alone plausibly bring M130 under
3.0s without touching any regulated gate, tax value, or index schema.

Source: Fable optimization-guru discovery pass 1 (2026-07-06), grounded in the
`2026-07-05-ledger-latency-budget-adr`, the ledger scale benchmark, and the real
read / write / registry paths. Rolling: subsequent sweeps append surfaces here.

### HEAD reconciliation - 2026-07-06 planning pass

Semantic search plus exact-symbol confirmation found that the current worktree already
contains the accepted O2 partition mechanism in `src/aeat/adapters/persistence/profile/transactions.py`.
The residual batch-read finding remains because both `load_for_date_range` and
`partition_by_date_range` still call `SecureObjectRepository.load` once per selected
transaction id. The secure-object implementation in
`src/aeat/adapters/persistence/storage/sql/secure_objects.py` has no targeted multi-load
API today.

The double-parse finding should be treated as partially mitigated. The timestamp witness
now reuses `_decode_persisted_transaction_row`, but the row still proceeds through
`Envelope[Transaction].model_validate_json(record.payload)` for JSON-mode validation.
That is still a second parse, but it is not the pre-fix independent guard parse Fable
described.

The write-path finding should be narrowed. Per-transaction secure-object rows and
hash-based reconciliation mean unchanged rows are not encrypted or upserted. However,
`_reconcile` still serializes and hashes every transaction in the incoming catalogue, so
single-row mutations still have an O(n) CPU/hash/index residual. Treat dirty-set writes
as a follow-up decision, not part of the read-path ADR.

Registry TTL should not be planned as a first implementation slice on this branch. Prior
performance work and `src/aeat/domain/calculations/registry/tests/test_authority.py`
already cover authority caching and invalidation. Keep it as a confirmation gate after
the ledger-specific residuals are measured.

### W01.P01.S01 execution confirmation - 2026-07-06

The current branch is already past the pre-O2 full-scan shape described in the older
review snapshot. The transaction catalogue repository exposes `partition_by_date_range`
with the accepted completeness gate: missing or stale date-index rows fall back to a
full catalogue load, while complete indexes decrypt only the selected in-window
transaction ids and return plaintext out-of-window stubs. The residual read-path cost
is therefore not the O2 decision itself, but the targeted-read implementation still
calling `SecureObjectRepository.load` once per in-window transaction id.

The timestamp witness finding is also narrower than the original "double parse"
wording. The repository now routes the persisted-row timestamp guard through
`_decode_persisted_transaction_row` and `_validate_persisted_transaction_timestamps`,
so the guard itself does not independently decode the same row bytes. A residual parse
remains because the authoritative envelope path still validates with
`Envelope[Transaction].model_validate_json(record.payload)`.

The write-path finding is narrowed in the same way. Per-transaction secure-object rows
plus `namespace_payload_hashes` prevent unchanged transactions from being rewritten,
but `_reconcile` still iterates every incoming transaction, serialises it, and computes
its payload hash before discovering that all but the changed row match storage. Treat
that as an O(n) mutation residual for W05 measurement, not as the older full-row rewrite
defect.

### W02.P05.S14 batch-read measurement update - 2026-07-06

The W02 batch-read slice replaced the indexed `load_for_date_range` and
`partition_by_date_range` per-id secure-object reads with one targeted `load_many` query
per selected window, while preserving the date-index completeness fallback. The same
scale benchmark now gives a concrete before/after for the M130 path:

- Pre-batch S03 baseline: `modelo_calculate_diagnostic` P95 `4.172s`,
  `partition_reads=4`, `partition_in_window_rows=7484`.
- Post-batch S13 measurement: `modelo_calculate_diagnostic` P95 `2.666s`, mean
  `2.036s`, min `1.634s`, max `2.666s`, `partition_reads=4`,
  `partition_in_window_rows=7484`.
- P95 delta: `-1.506s` (`36.1%` lower than the S03 baseline), bringing the measured M130
  diagnostic under the 3.0s target without changing regulated gate order, declared tax
  values, diagnostics semantics, or the plaintext date-index schema.

The S13 full-scan diagnostics remain out of scope for the batch-read slice and should be
treated as residuals for later validation/double-parse and annual-effective-date work:

- `ledger_read_diagnostic`: P95 `6.278s`, mean `6.115s`, n=3.
- `annual_renta_aggregation_diagnostic`: P95 `6.797s`, mean `6.435s`, n=3.

Operational note: the first S13 benchmark attempt failed while seeding the 30k-row
fixture because the default temp drive had about 78 MB free. The successful run pinned
`TEMP`, `TMP`, and `TMPDIR` to `.tmp-bench` on the workspace drive.

### W04.P12.S39 validator-fast-path measurement update - 2026-07-06

The W04 validator slice moved `Transaction` derived-id enforcement from the
Python-mode before-validator path to an after-validator over already validated
`raw`, removed the transaction-specific manual coercion helpers, and preserved
catalogue JSON roundtrips through JSON-mode nested transaction loading. The same
selected scale benchmark nodes were run after the validator rewrite:

- `ledger_read_diagnostic`: n=3, P95 `5.126s`, mean `4.969s`, min `4.691s`,
  max `5.126s`, out-of-scope full-catalogue read.
- `annual_renta_aggregation_diagnostic`: n=3, P95 `5.751s`, mean `5.379s`,
  min `5.144s`, max `5.751s`, out-of-scope pending invoice-date key.
- `modelo_calculate_diagnostic`: n=4, P95 `1.141s`, mean `0.961s`, min
  `0.835s`, max `1.141s`, `partition_reads=4`, `partition_in_window_rows=7484`.

Compared with the S13 post-batch-read baseline, the validator fast path produced:

- `ledger_read_diagnostic`: P95 delta `-1.152s` (`18.4%` lower).
- `annual_renta_aggregation_diagnostic`: P95 delta `-1.046s` (`15.4%` lower).
- `modelo_calculate_diagnostic`: P95 delta `-1.525s` (`57.2%` lower), while
  preserving the same partition read count and in-window row total.

The measured M130 calculate diagnostic is now well below the 3.0s target after
the combined batch-read, diagnostic-summary, and validator-fast-path work. Full
catalogue read and annual renta remain out-of-scope diagnostics and still need
the later double-parse / annual effective-date levers if they become budgeted
surfaces.

### W05.P13.S41 write-path attribution - 2026-07-06

The S40 benchmark added a real encrypted-SQLite single-transaction mutation
diagnostic over the same 30k-row scale fixture. It times the public
`repo.save(updated_catalogue)` path for a one-row, same-id update and separately
reports the two named O(n) components inside `_reconcile`:

- `transaction_save_namespace_hash_scan`: n=3, P95 `0.201s`, mean `0.195s`,
  min `0.192s`, max `0.201s`.
- `transaction_save_serialize_hash_all_rows`: n=3, rows=30000, P95 `1.399s`,
  mean `1.219s`, min `1.122s`, max `1.399s`.
- `single_transaction_save`: n=3, rows=30000, changed_rows=1, P95 `2.659s`,
  mean `2.497s`, min `2.210s`, max `2.659s`.

Conclusion: transaction serialization plus SHA-256 dominates the named residual,
not the namespace hash scan. The serialize+hash P95 is about `7.0x` the
namespace scan P95 and accounts for about `52.6%` of the measured save P95, while
the namespace scan accounts for about `7.6%`. The remaining save time is the rest
of the real write path: membership-index load, key digest work, changed-row
write construction, `apply_batch`, and the date-index sync transaction.

This confirms the dirty-set/cache decision surface should focus first on
avoiding all-row envelope serialization and payload hashing for known
single-row mutations, while preserving the existing decryption-free unchanged-row
skip and atomic batch write contracts.
