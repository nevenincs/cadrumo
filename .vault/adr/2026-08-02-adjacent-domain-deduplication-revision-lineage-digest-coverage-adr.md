---
tags:
  - '#adr'
  - '#adjacent-domain-deduplication'
date: '2026-08-02'
modified: '2026-08-02'
body_schema: 'body-v1'
body_hash: 'sha256:325c035594e612e0ddf313179303af5840d68c28f5aaa38def630a6c31ebd146'
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
- Multi-generation mirror lag is a structurally expected state, not an edge case. The
  push is an operator-invoked CLI verb, not a per-write hook, and it accepts
  `--namespace` and `--limit` filters that deliberately cover a subset of the store.
  Nothing bounds how far a namespace falls behind between pushes, and
  `build_revision_ancestor_ids` in `_secure_object_schema.py` carries the whole prior
  chain forward with a dedupe and no cap, so depth greater than one is the design's
  own expectation.
- `_is_stale_remote_entry` is a disjunction: the remote revision matches the local
  `previous_revision_id`, or it appears in the ancestor chain. The first disjunct is a
  derivation input and the second is not, so the two halves of one predicate carry
  different integrity properties, and only the second recognises lag beyond one
  generation.
- Of the other four, `revision_written_at` alone reaches production logic: it selects
  which entry becomes the manifest's `latest_revision_id` and
  `latest_revision_written_at` watermark. Neither watermark has a production consumer
  that gates on it. `write_provenance`, `source_event_id`, and `conflict_policy` are
  written, copied into quarantine rows by `_secure_object_integrity.py`, and read by
  nothing that decides anything.
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

- **A. Widen `derive_revision_id` to all nine stamped columns.** Rejected: the
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
- The pinned coverage test must not move under this decision. It pins what the digest
  covers; this record changes only where the gate runs. If that module reds, the change
  has drifted into option A or B.
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
keeps its eight inputs. The guarantee is restated in its own terms: the gate detects
corruption and partial tampering of the derivation tuple, and it is not an
authentication mechanism, because an unkeyed digest over a row's own columns cannot
authenticate that row against anyone who can write it. The already-corrected prose and
the pinned coverage test stand as they are, with the gate's classification as a
corruption detector made explicit alongside them.

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

The knockout is that the digest is unkeyed. Every remedy built on widening it assumes
the adversary can edit a column but cannot recompute a hash, and that assumption fails
for any adversary who has already reached the column — the algorithm is in the source
and every input is in the row. Options A and B therefore pay a full restamp of every
stored revision id for an attacker cost of one extra hash call. The only residual value
in widening is detection of accidental single-column corruption, and that is not a
failure mode this stack produces: the metadata stamp lands inside the same transaction
as the ciphertext insert, so a row with one drifted metadata column and everything else
intact is not a shape the writer can emit.

What made the ancestor column look like a digest-coverage problem was the assumption
that the gate runs on the mirror path. It does not. With exactly one production caller
on the decrypting read path, a tampered `payload_hash` — a column the digest does
cover — is refused on one path and served verbatim on the other. The mirror's exposure
was never the four-versus-nine split; it was that the mirror consults no lineage
verification whatsoever. Fixing where the gate runs recovers four columns on that path
for no persisted-format change, which dominates widening the digest to recover one
column on a path that would still not check it.

Keeping both disjuncts in `_is_stale_remote_entry` follows from the same reasoning
plus a capability argument. The disjunct that survives narrowing is not meaningfully
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

Running the gate on the mirror preflight will make some rows unpushable that are
pushable now. That is the intended direction, but it converts a silent pass into an
operator-visible blocking failure, so the failure text has to name the row and the
reason well enough to act on.
