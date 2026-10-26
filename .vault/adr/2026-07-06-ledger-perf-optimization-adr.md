---
tags:
  - "#adr"
  - "#ledger-perf-optimization"
date: '2026-07-06'
related:
  - "[[2026-07-06-ledger-perf-optimization-reference]]"
  - "[[2026-07-06-ledger-perf-optimization-research]]"
  - "[[2026-07-05-ledger-latency-budget-adr]]"
  - "[[2026-07-06-ledger-latency-budget-adr]]"
supersedes:
  - '2026-07-06-ledger-latency-budget-adr'
modified: '2026-07-17'
body_hash: 'sha256:430de795c80d17eb537d635ab9dfad4e7ac8e90aa1ee1442b0dcf7f9c1cde447'
---
# `ledger-perf-optimization` adr: `write-path serialization cost: dirty-set save vs serialization-carry cache` | (**status:** `accepted`)

## Problem Statement

Every ledger mutation — including a one-row `ledger add` / `update` / `classify` —
funnels into `TransactionCatalogueRepository.save`
(`src/cadrumo/adapters/persistence/profile/transactions.py:310`) or
`save_with_secure_object_writes` (`transactions.py:330`), whose `_reconcile`
(`transactions.py:671`) discovers the changed row by re-deriving content identity for
the ENTIRE catalogue: it re-parses the ~30k-id encrypted membership envelope
(`_load_index_ids`, `transactions.py:733`), re-serializes every transaction
(`_serialise_transaction`, `transactions.py:763` — one `model_dump_json` per row),
SHA-256s every payload (`transactions.py:698-699`), and compares against a
decryption-free `namespace_payload_hashes` store scan (`secure_objects.py:898`). After
the atomic `apply_batch` commit, `_sync_date_index` (`transactions.py:601`)
additionally re-reads every plaintext date-index row for the bucket
(`transactions.py:627-634`) to diff it against the full catalogue.

Measured at 30k rows / 10 filing years (W05.P13.S41 attribution in the
`2026-07-06-ledger-perf-optimization-reference`): `single_transaction_save` P95
`2.659s` for `changed_rows=1`; the all-row serialize+hash component alone is P95
`1.399s` (~52.6% of save P95, 7.0x the `0.201s` namespace hash scan). This cost is
absent from the accepted read-path `2026-07-05-ledger-latency-budget` ADR and all its
tracked residuals — the reference names it S2b, "the largest untracked cost".

A sibling proposed draft (`2026-07-06-ledger-latency-budget-adr`, status `proposed`)
recommended an additive dirty-set save API and rejected a bytes/hash cache. This ADR
re-opens that comparison with the full mutation-entry-point inventory and a cache
design the draft did not consider (identity-keyed load-to-save carry), and on
acceptance replaces that draft (to be marked superseded via
`vaultspec-core vault adr supersede`).

## Considerations

- **The full-reconcile is a correctness contract, not an implementation detail.**
  `save(catalogue)` guarantees storage converges to exactly the in-memory catalogue:
  the repository DERIVES the diff from content (fresh-serialization hash vs stored
  hash), deletes orphans bounded by the per-bucket membership index
  (`transactions.py:724-730`), rewrites the membership index only when the id set
  changed (`transactions.py:712-722`), commits everything (plus sibling bucket-event /
  invoice co-writes) in one atomic `apply_batch` (`secure_objects.py:924`), and then
  passively re-syncs the derived date index for the whole catalogue — the self-heal
  the read-path stale-index fallback docstrings rely on (`transactions.py:612-617`;
  rule `ledger-participation-index-is-derived-rebuildable`).
- **Change detection today trusts nothing but content.** Envelope bytes are
  deterministic because `written_at = transaction.modified_at`
  (`transactions.py:763-778`), so an unchanged row serializes to identical bytes and
  an identical hash. Critically, `modified_at` re-stamping on edit is an
  application-layer convention (`domain/transactions/_models.py:819`, stamped at
  `application/ledger/_actions_manual.py:559` and `:612`), not a structural
  guarantee — a content edit that failed to bump the stamp is still detected and
  written today, because the hash is computed from the actual content.
- **Mutation entry-point inventory (can each supply a dirty-set?).** The ledger
  command funnel `_save_transaction_catalogue_and_events` /
  `_save_transaction_catalogue_invoices_and_events`
  (`application/ledger/_actions_common.py:714` and `:732`) serves: manual add/update
  (`_actions_manual.py:168,517`), classify (`_actions_classification.py:267`),
  lifecycle review/remove/reset (`_actions_lifecycle.py:310,413,420,557,564,670`),
  split/merge (`_actions_split_merge.py:217,708`), export-state stamping
  (`_actions_export.py:138`), bulk statement import (`_actions_import.py:316`), and
  LLM bulk classification (`_llm_classification.py:632,1482`). All of these know
  their changed/removed ids (single subject; split parent plus children;
  import-summary ids; per-row classification results). OUTSIDE the funnel, whole
  rewritten catalogues are saved by invoice-transaction linking
  (`application/invoices/_linking.py:97`), invoice reconciliation
  (`application/invoices/_reconciliation.py:143`), profile bundle import/merge
  (`application/user_profile/_bundle.py:290-332`), and the sandbox bucket merge
  (`application/bucket_maintenance/_sandbox.py:652`). Dirty-sets are computable at
  each, but every call site becomes a place where an incomplete claim silently
  strands a stale row.
- **Frozen instances carry by identity from load to save.** `Transaction` and
  `TransactionCatalogue` are strict-frozen; every single-row mutation loads the
  catalogue in the SAME process (the CLI is process-per-command), rebuilds the
  mapping reusing the untouched loaded `Transaction` instances, and replaces only the
  edited entry with a NEW instance. An untouched row at save time is the very same
  object the repository deserialized. This is the hook a load-to-save carry can
  exploit without any cross-process cache.
- **No confidentiality dimension.** All 30k plaintext `Transaction` objects are
  already resident in memory for the command's lifetime; a hash memo adds only ~2 MB
  of 64-hex digests, never envelope bytes, and nothing leaves secure storage
  (`sensitive-financial-data-secure-storage-only` is untouched on the write side).
- **Concurrency shape.** `_reconcile` compares fresh serialization against a FRESH
  store scan at save time, which keeps it correct under a concurrent writer process.
  Any cache may therefore only ever stand in for the fresh-serialization side of the
  comparison — never for store-side state.
- **Governing rules:** `no-silent-under-declaration` (a silently-skipped changed row
  is exactly this class), `aeat-roundtrip-discipline` (parity and anti-tautology
  proof tests), `ledger-participation-index-is-derived-rebuildable` (index staleness
  may cost speed, never correctness).

## Considered options

- **O1 — status quo.** Correct and contract-complete; multi-second per one-row edit
  at 30k scale, worsening linearly. Rejected as a terminal state; retained as the
  semantic contract every option must preserve or explicitly supersede.
- **O2 — application-layer dirty-set save API** (the sibling draft's
  recommendation): callers pass changed rows plus removed ids; the repository
  serializes only those. Best ceiling (~O(changed) plus batch commit; est.
  0.2-0.4s), because it also removes the membership-envelope parse, the namespace
  scan, and the full date-index diff. Cost: changes the mutation contract from
  repository-derived truth to caller-asserted claims; an incomplete dirty-set is a
  stale row that loads with pre-edit values, silently — the named worst failure
  class. Weakens the date-index passive self-heal. Requires per-call-site dirty-set
  derivation for the four non-funnel bulk writers or a permanent two-path split.
  Kept — but as a GATED follow-up, not the first move.
- **O3 — repository-internal serialization-carry hash cache, identity-keyed
  (recommended).** At `load()`, memoize — per loaded frozen `Transaction`
  instance — the SHA-256 of the exact plaintext envelope bytes the row deserialized
  from. In `_reconcile`, an incoming transaction that IS (object identity) a
  memoized loaded instance reuses the memoized hash, skipping `model_dump_json` plus
  SHA-256; every other row, and every other step (fresh store scan, diff, deletions,
  membership index, `apply_batch`, date-index sync), is byte-identical to today.
  Removes the measured dominant `1.399s` component with zero contract change, zero
  caller change, and no new trust surface.
- **O4 — `(transaction_id, modified_at)`-keyed bytes/hash cache** (the reference's
  sketch; the sibling draft's O2). Rejected: the key imports a NEW invariant —
  "every content edit bumps `modified_at`" — that is today only a convention. A
  stamp-less content edit is written correctly today (its content hash differs);
  under O4 it would be silently skipped. O3 achieves the same win keyed on object
  identity, which cannot be wrong for a frozen instance.
- **O5 — contract-preserving residual micro-levers** (memoized membership-id parse
  within one save, targeted date-index diff querying only affected ids, batched HMAC
  key-digest derivation). Real but individually small; not decided here — named as
  the residual backlog behind the ~1.26s post-O3 estimate.

## Constraints

- **Operator sign-off is a hard gate on O2.** A dirty-set API changes repository
  mutation semantics (caller-asserted change claims replace repository-derived
  content diffs). NO dirty-set implementation may begin unless (a) a fresh post-O3
  paired benchmark still exceeds the write-latency budget the operator sets, AND (b)
  the operator explicitly accepts the escalation. This double gate is recorded here
  deliberately; accepting O3 does not carry O2.
- **O3 equivalence assumption, pinned by test.** O3 assumes fresh serialization of
  an untouched loaded instance is byte-identical to its stored plaintext bytes — the
  same dump determinism the existing diff already depends on
  (`transactions.py:766-768`). If a future pydantic upgrade shifted dump format, the
  uncached path would rewrite all rows once (converging bytes); the cached path
  would instead retain old-format bytes that still validate — semantically
  identical, but the equivalence must be pinned by a loud test (serialize a loaded
  fixture row, assert byte-equality with its stored payload) so a dump-format shift
  is a visible decision, not silent drift.
- **Identity keying must be identity-safe.** The memo must hold the instance
  reference and verify is-identity (or live alongside the instance), never a bare
  `id()` integer key that a garbage-collected object could vacate for a new
  instance.
- **The store-side comparison stays fresh.** The memo never substitutes for the
  save-time `namespace_payload_hashes` scan; concurrent-writer semantics are
  unchanged.
- **Parent-feature stability.** The per-transaction row store, membership index,
  atomic `apply_batch`, and date-index completeness gate are landed, accepted
  (`2026-07-05-ledger-latency-budget-adr`), and benchmark-covered; O3 builds
  strictly inside them. Benchmarks run on a shared machine — budget verdicts come
  from fresh paired runs of the S40 `single_transaction_save` diagnostic, not this
  ADR's projections.

## Implementation

High-level shape (not a plan):

- **Stage 1 (O3, on acceptance of this ADR):** a private memo on
  `TransactionCatalogueRepository`, populated during `load()` with the payload hash
  of each row's plaintext envelope bytes, keyed by the deserialized frozen
  `Transaction` instance; `_reconcile` consults it (with an identity check) before
  serializing a row, falling back to serialize-and-hash on any miss. Cache misses
  degrade to exactly today's behavior, so bulk writers that construct fresh
  instances (import, bundle merge, sandbox merge) are automatically correct, just
  uncached.
- **Stage 1 verification gates:** (a) a parity test asserting the memoized and
  memo-disabled `_reconcile` produce identical write/delete/membership-index sets
  across add, update, classify, split/merge, import, and invoice-link fixtures; (b)
  an anti-tautology proof — a content-changed replacement instance is detected and
  written — plus the byte-equivalence test pinning the loaded-bytes equals
  fresh-serialization assumption; (c) a fresh paired `single_transaction_save`
  benchmark run recorded against the S40 baseline.
- **Stage 2 (O2, doubly gated):** only if the post-Stage-1 measurement still
  breaches the operator's write budget: an ADDITIVE dirty-set method (changed rows
  plus removed ids plus sibling writes; deletions bounded by the membership index;
  full `save` retained as the fallback and repair boundary) per the sibling draft's
  shape, PLUS a compensating mechanism for the lost date-index passive self-heal (a
  staleness advisory or opportunistic full re-sync). Separate plan, separate
  operator acceptance.
- **On acceptance:** mark the sibling proposed draft
  `2026-07-06-ledger-latency-budget-adr` superseded by this record.

## Rationale

The measurement picks the first move. Serialize-and-hash-all-rows is ~52.6% of the
one-row save P95 and 7.0x the namespace scan; O3 removes exactly that component for
free — no contract change, no caller changes, no new invariant — because the
mutation paths already hold the loaded frozen instances in the same process. O2's
additional win (the remaining ~1.0-1.2s of membership parse, namespace scan, HMAC
digests, and date-index diff) is real but is bought with the project's most
expensive currency: a mutation contract whose failure mode is a silently stale
financial row (`no-silent-under-declaration`), a weakened derived-index self-heal,
and a per-call-site correctness obligation across eleven mutation entry points
including four bulk writers outside the ledger funnel. Buying the risk-free 53%
first and re-measuring before deciding whether the residual justifies the contract
change mirrors the staged shape the accepted read-path ADR used (partition first,
constant-factor levers later). The identity-keyed cache is chosen over the
`modified_at`-keyed variant precisely to preserve the property that change
detection derives from content and identity the repository itself established —
never from an application-layer stamp convention.

## Consequences

- **Good:** one-row mutation P95 estimated `2.659s` to ~`1.26s` at 30k rows with
  zero semantic change; every caller — funnel and bulk — benefits or degrades
  gracefully to current behavior.
- **Good:** the decision boundary is recorded: full-reconcile `save(catalogue)`
  remains THE mutation contract; any caller-asserted dirty-set requires explicit
  superseding operator sign-off, so the contract cannot erode by optimization
  drift.
- **Bad (accepted cost):** ~1.26s of O(n) residual remains (membership-envelope
  parse, namespace hash scan, per-row key digests, full date-index diff); at 100k+
  rows the Stage-2 escalation becomes likely rather than optional.
- **Bad (documented subtlety):** under a future dump-format shift the cached path
  retains old-format stored bytes instead of a one-time rewrite storm; benign under
  the no-legacy posture but pinned by the byte-equivalence test so it surfaces
  loudly.
- **Neutral:** the sibling proposed dirty-set draft is superseded on acceptance; the
  O5 micro-levers stay an unclaimed residual backlog.
- **Approval gate:** this ADR is `proposed`. Stage 1 (O3) may be implemented once
  this ADR is accepted. Stage 2 (O2, dirty-set) implementation is BLOCKED behind
  both a post-Stage-1 benchmark breach and explicit operator sign-off, because it
  changes repository mutation semantics.
