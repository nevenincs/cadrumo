---
tags:
  - '#adr'
  - '#adjacent-domain-deduplication'
date: '2026-08-02'
modified: '2026-08-02'
body_schema: 'body-v1'
body_hash: 'sha256:3bda08dd76eb70e36d65c36aee6ab8797845e64911280cdc4a4ffa9b65afde32'
related:
  - "[[2026-08-02-adjacent-domain-deduplication-fleet-burndown-findings-audit]]"
---

# `adjacent-domain-deduplication` adr: `keep the revision-lineage digest unkeyed and eight-input, and fix where the gate runs rather than what it covers` | (**status:** `accepted`)

## Problem Statement

`write_revision_metadata` in `_secure_object_row_codec.py` stamps ten columns on a
secure-object row; `derive_revision_id` in `_secure_object_crypto.py` mixes eight
inputs, four of which are among those ten. Excluding `revision_id` itself, five
stamped columns therefore sit outside the content address: `revision_ancestor_ids`,
`revision_written_at`, `write_provenance`, `source_event_id`, and `conflict_policy`.
A row whose stored value for any of the five is edited recomputes the same
`revision_id` and is admitted by `verify_revision_self_consistency`.

The uncovered set is not the whole of the ancestry story, and the precise shape
matters. `build_revision_ancestor_ids` prepends `previous_revision_id`, and that head
link is itself a derivation input, so the gate pins the parent edge and nothing behind
it. A forged chain therefore presents a *coherent* wrong lineage: the direct parent
still verifies while the history behind it is fabricated, which is a harder thing to
notice than an obviously broken chain.

One of the five is load-bearing rather than merely descriptive. `revision_ancestor_ids`
is read straight off the local row into the remote-mirror manifest, and
`_is_stale_remote_entry` in `_mirror_manifest.py` classifies a remote entry as stale
when the remote revision id appears in that chain. A stale classification is a
degradation and a conflict classification is a blocking failure, and only blocked
namespaces are withheld from the push. A forged ancestor entry therefore reclassifies
a genuine lineage fork as routine lag and the namespace is mirrored anyway.

The over-claiming prose that started this has already been corrected in place, so
what remains open is the structural question the correction deliberately left
standing: should the gap be closed, and at which layer. The window matters, because
`COMPATIBILITY_REGIME` is `PRE_RELEASE`, and any change that restamps stored revision
ids costs a bucket rebuild today and an upgrader, a pre-bump fixture, and a
restorability test after the checkpoint flip.

## Considerations

- `derive_revision_id` hashes with `sha256_hex`, which is plain `hashlib.sha256` in
  `core/hashing.py` — an unkeyed digest over columns of the same row. Every input it
  mixes is readable and writable by anyone who can write the row.
- The threat model that reaches all five columns is direct local database write
  access. There is no confidentiality break in it: the AEAD still authenticates and
  encrypts the payload, and the mirror carries ciphertext only.
- That access splits into two models, and they must be kept apart because the gate
  behaves differently under each. Against a *restamping* adversary — one who edits a
  column and recomputes `revision_id` — the gate is worthless for all ten columns, and
  its width is irrelevant. Against *partial tampering* — a buggy tool, a migration
  script, or an adversary who does not restamp — the gate catches the four covered
  columns and misses the five uncovered ones, and width is exactly what decides the
  split. Every claim below names which model it is made under.
- Under the partial-tamper model the gate is load-bearing, not redundant with the
  AEAD. The payload associated data binds only namespace, object-key digest, and
  schema version, so `written_at`, both content hashes, and both previous-revision
  links are protected here and nowhere else. A tampered `written_at` is refused, and
  this gate is its sole protection.
- `revision_id` is a linking value, not a standalone stamp: `previous_revision_id` and
  the ancestry chain reference it, and `expected_revision_id` reads it as an
  optimistic-concurrency guard. Restamping it is therefore a whole-chain rewrite
  across every referencing row, not a per-row column recompute.
- Folding actor-ish or clock-ish fields into identity collides with the project's
  idempotency rule for single-subject mutations, which deliberately keeps exactly
  those fields out of derived ids. Two writes identical in content but differing in
  `write_provenance` or `source_event_id` would derive different ids and stop
  collapsing on retry.
- `verify_revision_self_consistency` has exactly one production caller,
  `decode_secure_object_row` in `_secure_object_row_codec.py` — the decrypting read
  path. The mirror push consumes `iter_all_records_raw`, which by design bypasses the
  encrypted-column decorators so rows sealed under a rotated master key still surface,
  and never calls the gate. On the mirror path no lineage column is verified at all,
  including the four the digest covers.
- The ancestry chain is not reconstructible locally. The row carries a uniqueness
  constraint on namespace and object key and `write_revision_metadata` updates in
  place, so a superseded revision leaves no row to walk back to and
  `revision_ancestor_ids` is the only record of the chain beyond the direct parent.
- Multi-generation chains are the ordinary state, measured rather than inferred. A
  probe writing one object six times through the real repository grew the stored chain
  by exactly one entry per write, to depth five, against a single database row. Every
  object written three or more times carries a multi-generation chain.
- Nothing bounds mirror lag. The push has one production entry point, an
  operator-invoked CLI verb, with no scheduler, no per-write hook, and no background
  sync. `--limit` is refused on a real push, so a push is complete for the namespaces
  it covers, but `--namespace` is allowed, so a selective push leaves other namespaces
  behind. Lag resets on push and grows one generation per write between pushes, so a
  mirror more than one generation behind is the ordinary case, not an edge case.
- The frequency half of that question is not determinable from the repository. Actual
  operator push cadence is field data; nothing persists a push timestamp. What would
  settle it is a persisted push timestamp or the observed distribution of chain depth
  across real operator buckets.
- Nothing in the codebase exercises depth. `build_revision_ancestor_ids` in
  `_secure_object_schema.py` has no tests, and no fixture or test constructs a valid
  chain of length two or more; the new coverage gate performs two writes and reaches
  depth one.
- `revision_ancestor_ids` has exactly one decision-making consumer tree-wide,
  `_is_stale_remote_entry`. Every other site only carries it forward. It also grows
  without truncation, roughly one digest per write, re-serialised on every write, so
  its storage and write cost on a frequently-rewritten row is quadratic in the number
  of writes.
- `_is_stale_remote_entry` is a disjunction: the remote revision matches the local
  `previous_revision_id`, or it appears in the ancestor chain. The first disjunct is a
  derivation input and the second is not, so the two halves of one predicate carry
  different integrity properties, and only the second recognises lag beyond one
  generation.
- Of the other four, `write_provenance`, `source_event_id`, and `conflict_policy` are
  written, copied into quarantine rows by `_secure_object_integrity.py`, and read by
  nothing that decides anything. `conflict_policy` is a property of the write
  *operation* rather than of the revision, so it has no claim on identity at all.
- `revision_written_at` is UNRESOLVED, not cleared, and this record deliberately
  declines to resolve it on a partial trace. It reaches the mirror manifest and selects
  the watermark row, driving `latest_revision_id` and `latest_revision_written_at`.
  Searching for consumers of those two fields found no production site that decides on
  them — the same-named registry `latest_revision_id` is a different type on a
  different model and is not this value — but that search was not exhaustive enough to
  license a clearance. Separately, the column duplicates the `written_at` column that
  IS mixed, and the gate reads `written_at` and never `revision_written_at`, so whether
  it should exist at all is an open question this record does not answer.
- `_secure_object_integrity.py` does not cover the five. It copies them verbatim into
  quarantine and validates rows through `probe_row_decryptability`, which is an AEAD
  readability probe, not a lineage check.
- A keyed alternative already exists in the same package: `HashedLookup` in
  `_encrypted_columns.py` is HMAC-SHA256 under an HKDF sub-key of the master key.
- The current coverage split is pinned executably in
  `test_secure_object_revision_lineage_coverage.py`, which asserts both the covered and
  the uncovered set and states that the uncovered set is recorded, not endorsed. It is
  a tripwire against silent drift in either direction, not a prior refutation.

## Considered options

- **A. Widen `derive_revision_id` to every stamped column except `revision_id` itself, that is the four it already covers plus the five it does not.** Rejected: the
  derivation is unkeyed, so an adversary who can write the columns can recompute the
  wider digest exactly as easily as the narrower one. It raises the cost of the attack
  by one hash call and closes nothing, while restamping every stored revision id.
- **B. Widen the digest to `revision_ancestor_ids` only.** Rejected for the same
  knockout as A, at the same restamp cost, and for the additional reason that it does
  not bite where the harm is: the mirror path does not run the gate.
- **C. Narrow what `_is_stale_remote_entry` trusts, dropping the ancestor disjunct.**
  Rejected: it permanently caps recognised staleness at one generation, and
  multi-generation lag is the expected state under an operator-invoked, subsettable
  push. It also buys nothing against a deliberate adversary, because the surviving
  disjunct rests on `previous_revision_id`, forgeable by the same recomputation.
- **F. Drop the ancestor disjunct and delete the column outright.** Rejected as a
  consequence of rejecting C, not independently: it is the only coherent form of C,
  because the disjunct is the column's sole decision-making consumer and dropping one
  without the other would leave an unbounded, untrusted, unread column — the one
  indefensible outcome available here. It becomes live only if C is ever revisited.
- **G. Leave `revision_id` as the lineage address and attest the remaining stamped
  columns with a separate metadata MAC.** Deferred, and the strongest of the rejected
  family: it is the only option that protects audit attribution without redefining
  revision identity, without restamping any chain, and without the idempotency
  collision that sinks A. Not adopted now because nothing currently decides on the
  three cleared attribution columns, so the machinery would attest data no gate reads;
  it shares option D's key-availability dependency and is deferred on the same
  trigger.
- **D. Make the revision id a keyed MAC under a master-key sub-key.** Deferred, not
  rejected: it is the only option that actually defeats the stated threat model, but it
  couples verification to master-key availability, which collides with the
  rotated-master-key rationale that `iter_all_records_raw` exists to serve.
- **E. Run the existing gate on the mirror's raw rows, keep the digest and the mirror
  predicate as they are, and state the guarantee as corruption detection.** Chosen.

## Constraints

- Option E changes no persisted format. All eight derivation inputs are already
  present on the raw row, so no restamp, no bucket rebuild, and no durability-floor
  decision follows from it.
- The pinned coverage test stays green and unchanged under this decision, and that is
  a property of the ruling rather than an accident. It pins what the digest covers,
  while this record changes only where the gate runs, so nothing it asserts moves. It
  therefore keeps working as the tripwire it was built to be: had this record chosen A,
  B, or G, that module would have had to move in the same commit as the decision, and
  its reddening is the mechanism that would have forced the prose to follow. If it reds
  under the chosen option, the implementation has drifted into widening.
- Option D's cost is asymmetric across the compatibility checkpoint, so deferring it
  is a priced decision, not a free one. Its blocking dependency is the
  rotated-master-key read path, whose own rationale must be reconciled before keying is
  viable.
- Running the gate on the raw path must not break that read path: a row that fails
  lineage verification is a mirror-preflight concern, and the raw iterator's other
  consumers keep their current behaviour.

## Implementation

Two rulings, kept separate because the columns are not one problem.

The first governs the digest and the four descriptive columns. `derive_revision_id`
keeps its eight inputs. The guarantee is stated with its model attached: the gate is a
corruption and partial-tamper detector over the derivation tuple, and within that model
it is load-bearing — it is the only protection `written_at` has, since the payload
associated data does not bind it. It is not an authentication mechanism, because an
unkeyed digest over a row's own columns cannot authenticate that row against anyone who
can write it and recompute. Both halves must be said together; the second alone reads
as though the gate did little, which is the misreading this record exists to prevent.
The already-corrected prose and the pinned coverage test stand unchanged.

The second governs `revision_ancestor_ids` and the mirror. The blocking-bypass is real
and is closed at the layer where it is actually open: the mirror preflight runs
`verify_revision_self_consistency` against the raw row before a namespace is pushed,
routing a failure through the existing blocking-failures channel rather than a new
refusal shape. That restores the four covered columns to enforcement on a path where
none of them were checked, a strictly larger gain than widening the digest would have
produced on a path that never consults it. `_is_stale_remote_entry` keeps both
disjuncts. The residual — a forged ancestor chain reclassifying a fork as lag — is
accepted and recorded, bounded to an adversary with local database write access, with
no confidentiality consequence and no ability to hide a divergence, only to relabel it.

Keying is deferred with a stated trigger: adopt option D if lineage metadata ever
becomes an input to a filing or legal decision, or before the `COMPATIBILITY_REGIME`
flip, whichever comes first, and reconcile it against the rotated-master-key read path
at that time.

## Rationale

The rejection of widening rests on the threat model being stated, because the obvious
argument proves too much. Against a restamping adversary the digest is unkeyed, so
editing a column and recomputing `revision_id` costs one extra hash call and defeats
the gate at any width — but that argument devalues the four columns the gate already
covers just as completely, so it cannot on its own justify keeping the boundary where
it is. Taken alone it would argue the gate is pointless, which is false: under partial
tampering the gate is the sole protection for `written_at`, and that is real coverage
worth keeping.

So the decision turns on the partial-tamper model, where width genuinely matters, and
widening loses there on three independent grounds. The cost is not a column recompute
but a whole-chain rewrite, because `revision_id` is referenced by
`previous_revision_id`, by the ancestry chain, and by the `expected_revision_id`
concurrency guard. The benefit is close to nil, because three of the five uncovered
columns are read by nothing that decides anything, one is unresolved, and the
consequential one is handled below by a cheaper route. And for two of them the change
is affirmatively harmful: folding `write_provenance` or `source_event_id` into identity
would give two content-identical writes different ids, breaking the idempotent-retry
collapse that the project's single-subject mutation rule deliberately protects by
keeping actor-ish and clock-ish fields out of derived ids.

The corollary is that width was never the reason the digest is forgeable — the absence
of a key is. That is why options D and G, not A and B, are the ones held open.

What made the ancestor column look like a digest-coverage problem was the assumption
that the gate runs on the mirror path. It does not. With exactly one production caller
on the decrypting read path, a tampered `payload_hash` — a column the digest does
cover — is refused on one path and served verbatim on the other. The mirror's exposure
was never the four-versus-nine split; it was that the mirror consults no lineage
verification whatsoever. Fixing where the gate runs recovers four columns on that path
for no persisted-format change, which dominates widening the digest to recover one
column on a path that would still not check it.

Keeping both disjuncts in `_is_stale_remote_entry` follows from the same reasoning
plus a measured capability argument. One-generation staleness is not enough: an object
written twice between two pushes already exceeds it, and that is the ordinary case
under an operator-invoked push with no bound on the interval. Capping recognition at
one generation would therefore reclassify routine lag as a conflict and block ordinary
pushes, which is a worse failure than the forgery it would prevent. The disjunct that survives narrowing is not meaningfully
more trustworthy than the one removed, so narrowing trades an integrity gain a
deliberate adversary sidesteps against a permanent cap on staleness recognition — and
because prior revisions are overwritten in place, that cap cannot be recovered by
walking history later. Against accidental chain corruption the running gate is the
better instrument; against a deliberate adversary only keying works, and keying is a
separate decision with a real architectural dependency rather than a parameter of this
one.

## Consequences

The guarantee becomes honest and executable in the same place. The gate is documented
as what it is, and it starts running on a path where it never ran, so the four covered
columns gain enforcement they did not have during mirror push.

The residual is named and survives. A forged `revision_ancestor_ids` can still
reclassify a lineage fork as routine lag and let a namespace be mirrored, and forged
`write_provenance`, `source_event_id`, `conflict_policy`, and `revision_written_at`
still misattribute an audit trail. This record accepts that consciously rather than
appearing to have closed it.

The pre-release window closes on the only remedy that would close the residual. After
the compatibility checkpoint, keying the derivation acquires an upgrader, a pre-bump
fixture, and a restorability test on top of the restamp. Deferring is therefore priced,
and the trigger is written down so the price is paid deliberately or not at all.

A latent tension is surfaced for whoever takes up keying: verification under a keyed
digest needs the master key, and the raw iterator exists precisely to surface rows when
the key has rotated. Those two cannot both hold unchanged, and that reconciliation is
the real blocking dependency on option D — not the restamp, which is cheap today.

Two questions are left explicitly open rather than resolved by this record. Whether
`revision_written_at` should exist at all is one: it duplicates the mixed `written_at`
column, the gate never reads it, and its only reach is a manifest watermark on which no
production decision was found — but that trace was not exhaustive, so it is recorded as
unresolved and not as cleared. The other is attribution: options D and G both remain
open on the same key-availability trigger, and G is the cheaper of the two if the need
turns out to be attribution rather than identity.

One defect this record does not close, and deliberately names rather than absorbing
into the decision: the ancestor chain grows without truncation, so a frequently
rewritten row pays quadratic storage and re-serialisation cost in its own write count.
The remedy shape is a bounded chain, and choosing the bound is the part that cannot be
settled here — a cap shorter than real mirror lag reintroduces exactly the blocking
misclassification that rules out option C, and the push cadence that would size it is
field data the repository does not hold. The interim position is therefore to leave
the chain uncapped, because an uncapped chain fails toward correct classification while
an undersized cap fails toward blocking a legitimate push, and to size a cap only once
push-cadence evidence exists. Pre-release keeps that change cheap whenever it is taken.

Running the gate on the mirror preflight will make some rows unpushable that are
pushable now. That is the intended direction, but it converts a silent pass into an
operator-visible blocking failure, so the failure text has to name the row and the
reason well enough to act on.
