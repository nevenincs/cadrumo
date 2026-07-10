---
tags:
  - '#adr'
  - '#ledger-latency-budget'
date: '2026-07-05'
modified: '2026-07-08'
related:
  - "[[2026-06-10-ledger-filter-period-adr]]"
  - "[[2026-07-06-ledger-perf-optimization-research]]"
---

# `ledger-latency-budget` adr: `period-scoped aggregation latency: gate reordering vs plaintext-index widening` | (**status:** `accepted`)

> **Operator decision (2026-07-06):** Path A (O2) accepted for implementation. The
> out-of-window diagnostic-taxonomy ruling — out-of-window rows report a uniform
> `OUTSIDE_PERIOD` in place of a refined per-row reason, with declared tax values
> provably invariant and the plaintext index schema unchanged — is signed off. Path B
> (O3) index-widening remains rejected on the recorded confidentiality grounds; any
> future proposal to add a classification column to `TransactionDateIndexRow` must
> supersede this ADR. Implementation proceeds under the mandatory index-completeness
> gate (stale index → full-scan fallback, never a silent drop) with full-scan-vs-partition
> parity tests; `_renta_ledger.py` stays on full `.load()` pending #599; the unfiltered
> full-catalogue listing read is out of scope (separate pagination/streaming lever).
>
> **Diagnostic-summary amendment (2026-07-06):** The O2 diagnostics contract now also
> permits each repository-backed resolver to collapse the uniform out-of-window
> `OUTSIDE_PERIOD` rows into one summary diagnostic carrying only the excluded-row count
> and filing-date span. The summary is diagnostics-channel only: it must not change any
> in-window observation, casilla value, provenance row, regulated gate order, plaintext
> date-index column, or stale-index full-scan fallback. It must not carry decrypted
> financial fields such as amount, counterparty, direction, category, lifecycle state, or
> business classification. If callers need row-level inspection, they must query the
> relevant period or use a dedicated ledger listing path rather than forcing every
> calculate call to allocate one diagnostic object per excluded transaction.

## Problem Statement

Issue #408 requires period-scoped ledger operations at 30k-transaction / 10-filing-year
scale to meet a documented 3.0s P95 latency budget. The correctness half of #408 is
closed and reviewed: all five ledger aggregators read the full encrypted catalogue via
`TransactionCatalogueRepository.load()`, so the `OUTSIDE_PERIOD` silent-under-declaration
bug class is eliminated. The performance half is NOT met. The standing benchmark
(`src/aeat/application/aggregation/tests/test_ledger_scale_benchmark.py`, 30k tx / 10
years, n=20, nearest-rank P95, real adapters) measured in the latest #408 pass: ledger
read P95 7.204s, modelo calculate (M130, 24 quarters) P95 7.828s, and the then
index-backed annual expense aggregation P95 3.883s (mean 2.824s) — all over 3.0s.

Root cause: every aggregation decrypt-scans the full per-bucket catalogue because the
period/date fact lives only inside the encrypted payload. A plaintext routing index
exists — `TransactionDateIndexRow` (`src/aeat/adapters/persistence/storage/sql/_orm.py`,
exactly five columns: `id`, `bucket_id`, `transaction_id`, `filing_date`,
`filing_year`; schema locked by live-table introspection in
`test_transaction_date_index.py`) — served through
`TransactionCatalogueRepository.load_for_date_range`
(`src/aeat/adapters/persistence/profile/transactions.py:336`). The simple approach,
pre-filtering each aggregator's input with `load_for_date_range`, was implemented,
proven wrong, and reverted (commit `765288da2e`; regression tests in `34ef174865`):
pre-filtering makes the `OUTSIDE_PERIOD` diagnostic structurally unreachable (an
observable behaviour change caught by
`test_repository_backed_aggregation_emits_casilla_01_sum`), and on the `_renta_ledger`
path it silently drops legitimately in-scope expenses whose linked invoice issue date is
in-window while the transaction's own date is not (issue #599). At HEAD, all five
aggregators therefore carry an explicit "NOT pre-filtered by date range" comment and pay
the ~7s full scan. This ADR decides the architectural path that closes the perf gap
without reopening the correctness gap.

A load-bearing profiling fact: AES-256-GCM decryption is only ~0.5s of the ~7s
full-scan cost for 30k rows; the dominant cost is per-row pydantic validation plus
content-hash identity verification. Both candidate paths win by shrinking the number of
rows that undergo decrypt-and-validate, not by making crypto faster.

## Considerations

- The four transaction-dated aggregators run classifier gates in a fixed order, and the
  `OUTSIDE_PERIOD` check is never first in the effective sequence:
  - `_iva_ledger.py`: the caller loop silently skips non-`ACTIVE` `lifecycle_state`
    (line 396) and `REVIEWED_EXCLUDED` `business_classification` (line 398) BEFORE
    `_classify_iva_transaction` checks `OUTSIDE_PERIOD` first-thing (line 470), ahead
    of the currency / direction / business / category / D5 counterparty gates.
  - `_renta_income_ledger.py` `_classify_income_transaction` (line 388): silent
    `REVIEWED_EXCLUDED` skip, then silent non-`INCOMING` skip, then currency issue,
    then `trabajo` routing issue (`TRABAJO_INCOME`), then personal/unclassified issue,
    then `OUTSIDE_PERIOD` LAST (line 452). Caller silently skips non-`ACTIVE`.
  - `_renta_gasto_ledger.py` `_classify_gasto_transaction` (line 257): silent
    non-`OUTGOING` skip, then silent personal/unclassified skip, then currency issue,
    then `OUTSIDE_PERIOD` (line 297), then `MISSING_TAXABLE_BASE` issue.
  - `_impatriado_income_ledger.py` `_classify_impatriado_income_transaction` (line
    279): silent `REVIEWED_EXCLUDED` skip, then silent non-`INCOMING` skip, then
    currency, then Beckham source-jurisdiction segregation (lines 318-341, deliberately
    ordered BEFORE the window gate per its docstring), then personal/unclassified,
    then `OUTSIDE_PERIOD` (line 358).
- Consequence: whether an out-of-window row is silent, gets a non-period issue, or gets
  `OUTSIDE_PERIOD` today depends on DECRYPTED fields (`direction`,
  `business_classification`, `lifecycle_state`, `irpf_category`,
  `source_jurisdiction`, currency). An index-only `OUTSIDE_PERIOD` for every
  out-of-window id fabricates diagnostics for rows that would have been silently
  skipped — confirmed empirically in the #408 thread (an out-of-window `OUTGOING` row
  produces zero observations AND zero issues from the real income aggregator).
- The critical structural fact both paths share: for IN-WINDOW rows, the date predicate
  is independent of every other gate and the classifiers are pure per-row functions.
  Partitioning the catalogue by date FIRST and running the unchanged classifier over
  only the in-window subset provably preserves every observation, casilla total, and
  provenance row (the declared tax values). The only observable delta is the ISSUE
  taxonomy for OUT-OF-window rows.
- The fifth aggregator, `_renta_ledger.py` (M100 annual expense), is excluded from any
  date-index optimisation until #599 is resolved: its effective filing date prefers the
  linked invoice's `invoice_issue_date` over the transaction's own date (line 276
  comment), so the transaction-date index is the wrong pre-filter key for it.
- Index freshness becomes correctness-bearing under either path: `_sync_date_index`
  (`transactions.py:457`) runs as a separate transaction after the encrypted commit,
  and `_date_index_candidate_ids` (line 429) falls back to full scan only when the
  bucket has ZERO index rows. A partially stale index would drop a row from both the
  decrypt set and the diagnostic set — the exact silent-drop class the correctness half
  closed. Any adoption must add a per-read completeness gate.
- Governing rules: `aeat-safety-legal-gates` and `registry-calculation-legal-grounding`
  (regulated classification semantics must not drift), `no-silent-under-declaration`
  (the diagnostic must surface), `sensitive-financial-data-secure-storage-only` (the
  plaintext boundary of the secure store), and
  `ledger-participation-index-is-derived-rebuildable` (derived caches must not carry
  correctness on freshness alone). The operator has repeatedly reserved
  confidentiality-boundary decisions.
- Budget scope: the 3.0s budget binds the period-scoped operations Kent's success
  moment names (period aggregation, modelo calculate). The unfiltered full-catalogue
  listing read (P95 7.204s) inherently touches every row and is out of scope for both
  candidate paths; it needs a separate lever (pagination/streaming).

## Considered options

- **O0 — status quo (full scan everywhere).** Correct; fails the budget by 2.4-2.6x on
  every measured operation. Rejected.
- **O1 — index pre-filter without diagnostic (the failed simple approach).** Fastest
  and simplest; silently drops `OUTSIDE_PERIOD` and (via #599) in-scope expenses.
  Already implemented, caught, reverted, and regression-locked. Rejected.
- **O2 — Path A: period-first partition with index-served `OUTSIDE_PERIOD`, index
  schema unchanged.** The repository partitions ids by the plaintext date index; only
  in-window rows are decrypted and classified by the UNCHANGED gate sequence;
  out-of-window rows are diagnosed `OUTSIDE_PERIOD` from plaintext (id + date) without
  decryption. Declared tax values provably invariant; the out-of-window issue taxonomy
  coarsens to a uniform `OUTSIDE_PERIOD`. **Recommended.**
- **O3 — Path B: widen the plaintext index with `lifecycle_state` and
  `business_classification`, then reorder as in O2.** Restores silent-skip fidelity for
  the two status gates (non-`ACTIVE`, `REVIEWED_EXCLUDED`, gasto's personal skip) on
  out-of-window rows. Identical perf to O2; widens the plaintext confidentiality
  surface; still does NOT restore full taxonomy fidelity (direction, `irpf_category`,
  `source_jurisdiction`, currency remain encrypted). Rejected.
- **O4 — full-fidelity index widening (direction + irpf_category +
  source_jurisdiction + currency + more).** The logical endpoint of the O3 ratchet;
  reconstructs a plaintext shadow ledger of fiscal-routing metadata. Rejected outright.
- **O5 — orthogonal cost levers (cheaper per-row validation on the load path, parallel
  decrypt/validate workers, long-lived process cache).** Reduce the per-row constant
  rather than N; decryption is already ~0.5s/30k so validation dominates. Not a
  substitute (a 2.4x constant-factor win across the board is not credible from
  validation tuning alone), but the natural follow-up lever if annual-window operations
  stay borderline after O2. Kept as complement, out of this decision's scope.

## Constraints

- **Operator sign-off is a hard gate on implementation.** O2 changes the out-of-window
  diagnostic taxonomy of a legally-flavoured channel (the `no-silent-under-declaration`
  issue surface), and O3/O4 would widen the plaintext boundary of the secure store — a
  decision class the operator has explicitly reserved. This ADR is the decision
  artifact; NO implementation may begin until the operator accepts the recommendation
  (status flips to `accepted`) or redirects it.
- **Index completeness gate must land in the same change as any reorder.** Before
  trusting the index for a partition, the repository must verify the bucket's index row
  count equals the secure-object membership index count; on mismatch, fall back to the
  full decrypt scan (correctness preserved) and surface a rebuild advisory
  (`rebuild_date_index` exists, `transactions.py:412`). Without this, a crash between
  the encrypted commit and the separate index-sync transaction reintroduces the
  silent-drop class.
- **`_renta_ledger.py` is out of scope** until #599 (invoice-issue-date fallback vs
  transaction-date index key) is decided; it stays on full `.load()`.
- Parent-feature stability: the date index, its schema-lock and fallback tests, the
  per-window memoization in `_MemoizedTransactionCatalogueRepository`
  (`src/aeat/application/modelo/_calculation_actions.py`), and the scale benchmark are
  all landed and green. The benchmark runs on a heavily shared machine; large
  run-to-run variance is documented in the #408 thread, so the budget verdict at
  implementation time must come from fresh paired runs, not from this ADR's
  projections.
- Diagnostic issue models cap `detail` at 512 chars; index-served issue details must
  respect it (a prior #408 fix hit exactly this cap).

## Implementation

High-level shape of the recommended O2 (not a plan):

- **Repository layer:** a partitioned read on `TransactionCatalogueRepository` that,
  given a `[start, end]` window, (1) runs the completeness gate (index count vs
  membership count; mismatch means full-scan fallback), (2) selects in-window ids from
  `TransactionDateIndexRow` and decrypts only those rows, and (3) returns the
  out-of-window remainder as plaintext `(transaction_id, filing_date)` stubs — no
  decryption, no payload fields.
- **Aggregator layer (4 modules):** each repository-backed entry point requests the
  partition for its existing window (IVA: the period span; M130 income/gasto: the
  cumulative RD 439/2007 art. 110.2 window; impatriado: the ejercicio). Out-of-window
  stubs map to uniform `OUTSIDE_PERIOD` issues whose detail states the date fact and
  that classification was not evaluated ("excluded by period before classification").
  In-window rows flow through the existing classifier functions byte-for-byte
  unchanged — every regulated gate (Beckham art. 93.2 segregation, trabajo vs
  actividad-económica routing, IVA D5 counterparty coupling, `REVIEWED_EXCLUDED`
  short-circuit ahead of the actividad-económica override) keeps its current order and
  semantics for every row that can contribute to a casilla. The internal date gates
  remain as defence-in-depth backstops.
- **Diagnostic-summary layer (amended 2026-07-06):** after the uniform O2
  `OUTSIDE_PERIOD` classification is established, resolvers may represent the
  out-of-window remainder as one summary diagnostic per resolver/window instead of one
  issue per excluded row. The summary carries the excluded count and minimum/maximum
  filing date only. Empty remainders emit no summary. Complete-index and fallback
  partitions must produce the same summary shape for the same catalogue.
- **Calculate path:** the existing per-window memoization already collapses the M130
  income+gasto pair onto one shared windowed scan per calculate call; no new mechanism.
- **Verification:** per-aggregator parity tests asserting full-scan result equals
  partitioned result for observations, casilla totals, and provenance on multi-period
  catalogues; updated out-of-window visibility tests pinning the new uniform taxonomy
  (including the previously-silent shapes: out-of-window `OUTGOING`, `ARCHIVED`,
  `REVIEWED_EXCLUDED` rows now appear as `OUTSIDE_PERIOD`); an anti-tautology
  staleness test (delete one index row, assert the completeness gate forces full-scan
  fallback rather than a silent drop); summary tests pinning count/date-span parity
  without per-row diagnostic allocation; fresh paired benchmark runs against the 3.0s
  budget.

## Rationale

**Perf: the two paths are equivalent, so perf cannot pick between them.** Both O2 and
O3 decrypt-and-validate only the in-window subset. Grounded projection from the
measured data (~7.2s P95 for 30k rows; the sole index-backed datapoint: a 3k-row annual
window at mean 2.824s / P95 3.883s INCLUDING invoice-catalogue loading and evidence
reconciliation on the `_renta_ledger` path): a quarterly IVA window (~750 of 30k rows)
projects well under 1s of windowed load — comfortably under budget; an M130 Q4
cumulative window (~3k rows) projects ~2-3s — under budget in the mean, borderline at
P95 on the shared machine; modelo calculate, currently 7.828s P95 dominated by one
full-scan load per quarter, projects ~2.5-4s once that load is windowed — at or under
budget, with O5 (validation cost) as the named follow-up lever if the annual-shaped
windows stay borderline. The unfiltered full-catalogue read stays over budget under
every option here and is explicitly re-scoped to a separate pagination/streaming lever.

**Risk: the decisive asymmetry.** O2's entire residual risk is confined to the
DIAGNOSTIC channel for rows that cannot contribute to any casilla (out-of-window rows),
and the gate-order analysis shows the declared-value invariance is provable by
construction plus parity test — there is no wrong-tax hazard, because no regulated
gate's order changes for any row that reaches an observation. O3's risk sits on the
CONFIDENTIALITY boundary, and the rigorous reading is unfavourable: `lifecycle_state`
(`ACTIVE`/`ARCHIVED`/`STASHED`/`SPLIT`) is genuinely workflow-only and leaks little
beyond the per-date row pattern the index already exposes, but
`business_classification` is a fiscal-relevance judgement — a plaintext per-row
`BUSINESS`/`PERSONAL`/`MIXED`/`REVIEWED_EXCLUDED` flag partitions the taxpayer's dated
transaction set into tax-meaning classes. An adversary with file-system access (the
gestor multi-client hosting scenario the secure-storage rule records as its motivating
exposure) would read business-activity volume, its temporal distribution, the
personal-vs-business ratio, and the operator's exclusion decisions — profile-level
facts about the taxpayer's financial affairs that dates alone do not reveal. That is
inside the spirit of `sensitive-financial-data-secure-storage-only` even though status
enums are outside its letter (which enumerates document bytes and amounts), and the
index's own schema contract ("no other financial content may ever be added") plus its
introspection lock were authored to hold exactly this line. Worse, O3's purchase is
poor: even after paying that cost, out-of-window rows gated on `direction`,
`irpf_category`, `source_jurisdiction`, or currency STILL coarsen to `OUTSIDE_PERIOD`,
so full taxonomy fidelity is only reachable via O4's shadow ledger. A widening that
buys partial fidelity and establishes the ratchet precedent is a bad trade against a
diagnostics-channel semantic ruling that buys the same performance for free.

**The O2 taxonomy change is defensible on its own terms.** `OUTSIDE_PERIOD` exists to
tell the operator "your catalogue holds rows beyond the window you queried" — the
uniform period-first ruling makes that signal MORE complete (previously-silent
out-of-window rows now surface) and factually precise (the date fact comes from the
same plaintext field every aggregator already filters on). What is lost is the per-row
refinement of WHY the row would also have been ineligible — a refinement that is
irrelevant to the queried period's filing and remains fully available by querying the
row's own period. The known costs are honestly ownable: `REVIEWED_EXCLUDED` rows
resurface in the out-of-window issue list (a bounded tension with that state's
"stop surfacing it" contract), and `SPLIT` parents can co-report with their children;
both are presentational and can be mitigated downstream (summary counting) without
touching the contract. We will therefore adopt O2: period applicability is decided
first, from the plaintext date, and terminates classification for out-of-window rows.
This is precisely the kind of semantic ruling that requires the operator's sign-off,
which this ADR requests.

## Consequences

- **Good:** period-scoped aggregation and modelo calculate are projected under or at
  the 3.0s budget with zero change to any declared tax value, zero change to the
  encrypted-store plaintext surface, and the five-column index contract intact. The
  reorder makes the `OUTSIDE_PERIOD` signal uniform and total over the catalogue.
- **Good:** the confidentiality boundary question is settled negatively and recorded:
  the date index does not grow classification columns; future "just one more routing
  enum" proposals must supersede this ADR rather than drift past the schema-lock test.
- **Bad (accepted cost):** the out-of-window diagnostic taxonomy coarsens — operators
  and downstream tooling see `OUTSIDE_PERIOD` where they previously saw silence,
  `TRABAJO_INCOME`, `BECKHAM_FOREIGN_SOURCE_SEGREGATED`, or currency issues on
  out-of-window rows. After the 2026-07-06 amendment, high-volume calculate paths may
  report those rows as one count/date-span summary, so consumers that depended on
  per-row out-of-window issue counts need a coordinated sweep.
- **Bad (new dependence, mitigated):** correctness of the diagnostic set now rides on
  index completeness; the mandatory per-read count-parity gate with full-scan fallback
  bounds this to "stale index = slow but correct", never "stale index = silent drop".
- **Neutral / deferred:** `_renta_ledger.py` (#599) stays on the full scan and its
  operation remains borderline; the unfiltered ledger listing remains over budget
  pending a pagination/streaming decision; O5 validation-cost work is the named lever
  if fresh benchmarks show annual windows still crossing 3.0s at P95.
- **Pathway:** once the completeness-gated partition API exists, the same mechanism
  can serve other period-scoped readers (participation queries, filing snapshots)
  without new confidentiality analysis.
