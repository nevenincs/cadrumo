---
tags:
  - '#adr'
  - '#code-dedup-sweep'
date: '2026-07-25'
modified: '2026-07-25'
related:
  - "[[2026-07-25-code-dedup-sweep-rag-inventory-audit]]"
---

# `code-dedup-sweep` adr: `inner-envelope version check is an equality, armed before the first bump` | (**status:** `accepted`)

## Problem Statement

Every persisted secure-object read passes two version checks. Layer one guards the
outer SQL row: `ensure_schema_version_readable` in
`adapters/persistence/storage/_schema_lineage.py:98` is a ceiling plus an
upgrade-chain completeness test, applied on every load through
`storage/sql/_secure_object_row_codec.py:156`. Layer two guards the inner
`Envelope` that lives inside the decrypted payload, and its canonical contract is
strict EQUALITY — `storage/envelope/_envelope.py:261` and
`storage/envelope/_secure_repository.py:195` both compare `!= max_supported_version`.
Equality is the right contract there precisely because layer one has already
refused or chain-upgraded the row, so an inner deviation is drift or corruption
rather than a lineage gap.

Twenty production read paths implement layer two as `schema_version > <constant>`
instead. A below-current inner stamp therefore passes silently at those sites and
its payload flows onward into filing and calculation surfaces. The decision is
whether to tighten the comparison, and it must be made now rather than deferred:
the edit is a provable no-op under today's constants and becomes a behaviour
change against filed taxpayer data the moment the first real version bump lands.

## Considerations

- The inventory of "22 sites" over-counts by two, and both exclusions are
  informative. `application/bucket_maintenance/_service.py:149` is not an instance
  of the defect but the canonical CORRECT shape: its ceiling at `:149` is paired
  with a below-floor refusal at `:157`, and the archive tier pins
  `_ARCHIVE_DURABILITY_FLOOR == _ARCHIVE_SCHEMA_VERSION == 3` (`:118`, `:123`), so
  the pair is exactly equivalent to `!= 3`. The encrypted-bundle gate at
  `application/user_profile/_bundle_encryption.py:91` likewise pairs its ceiling
  with a set-membership floor at `:99` against
  `SUPPORTED_BUNDLE_SCHEMA_VERSIONS`, and its own axis constant is
  `_ENCRYPTED_BUNDLE_ENVELOPE_SCHEMA_VERSION = 1` (`:20`) on a `ge=1` field
  (`:34`). Both are out of scope; the bundle tier's own two-sided gate at
  `application/user_profile/_bundle.py:121` and `:131` is the same correct shape.
- The remaining twenty sites are VACUOUS today, provably rather than by
  inspection. All 66 registered secure-object namespace definitions carry
  `schema_version = 1` (`SECURE_OBJECT_SCHEMA_VERSION_V1` at
  `storage/_namespace_registry.py:19`), and every one of the twenty validates the
  canonical `Envelope`, whose `schema_version: int = Field(ge=1)`
  (`storage/envelope/_envelope.py:174`). The below-current region is therefore
  empty, and `> 1` and `!= 1` are the same predicate on the representable domain.
- No legitimate write path can produce a below-current inner stamp. At every one
  of the twenty sites the writer stamps the identical namespace constant its
  reader compares — the pattern is visible as `schema_version=_X_VERSION` beside
  each `envelope.schema_version > _X_VERSION`. The only version pass-through
  writer found anywhere nearby, `application/workflow/_persistence.py:270`, feeds
  a diagnostic reset fingerprint from ROW metadata and persists no envelope.
- The asymmetry that gives the defect its future teeth: the row codec re-stamps
  the OUTER record to `max_supported_version` unconditionally
  (`storage/sql/_secure_object_row_codec.py:203`), while the inner stamp lives in
  the payload bytes and changes only if a registered upgrader rewrites that field.
  After a real bump, an upgrader that transforms payload shape but forgets the
  inner version yields exactly a below-current inner stamp on a record the outer
  layer has already declared current. Under `!=` that refuses loudly on first
  read; under `>` it is accepted silently.
- Nothing currently guards that hop. The seven tests in
  `storage/tests/test_schema_lineage.py` cover layer one only — chain
  completeness, future refusal, hop ordering — and no gate anywhere asserts that
  an upgrader re-stamps the inner envelope or constrains the inner check's shape.
- The regime argues FOR tightening. `no-legacy-compatibility` separates "Refuse,
  do not tolerate" (mandated) from "invent handling for shapes nothing wrote"
  (forbidden); a tightened refusal adds no read-tolerance and no handling, so it
  sits in the blessed half. `compatibility-lifecycle` states directly that
  constants, gates, empty registries, and scaffolds are installable now.
- The heterogeneous error surface is deliberate and load-bearing. Six profile
  sites raise `ModeloError` and `BucketsError` descendants with their own
  translated message and a reason plus stored-and-max-version context; others
  raise `EnvelopeVersionError` carrying per-object identity. One site is
  ordering-sensitive: the raise at
  `adapters/persistence/profile/usage_ratios.py:88` sits inside a `try` whose
  `except (ClassificationError, EnvelopeVersionError)` re-raises
  `UsageRatioPersistenceError`, so any shared helper that raises would silently
  re-route that path.

### Re-verified at HEAD `7058ef827f`, with two corrections to the inventory above

Semantic search was unavailable for this ruling. The code index was truncated
throughout the window (roughly 1027 chunks against roughly 4546 files) while
reporting `degraded_reasons: []`, so a miss carries no evidential weight. Every
claim below was re-established by `rg` over the tree and by reading both sides of
each site — never by a semantic probe, and never by trusting the inventory above.

The twenty sites are confirmed live and unchanged at HEAD. Enumerated:
`adapters/persistence/profile/` — `modelos_filing.py:174`,
`modelos_verification_reports.py:153`, `modelos_calculation.py:182`,
`buckets.py:176`, `modelos_work_units.py:154`, `participation_index.py:129`,
`transactions.py:316`, `filing_amendments.py:132`, `invoices.py:132`,
`usage_ratios.py:88`; `adapters/outbound/aeat/sede/_observation_store.py:192`,
`:219`, `:291`, `:320`; `application/workflow/_persistence.py:146` and `:411`;
`application/user_profile/_repository.py:295` and `:484`;
`application/live/_verify.py:252`; `application/live/_snapshot_base.py:489`. The
only drift from the record above is `participation_index.py`, at `:129` rather
than `:130`.

**Correction 1 — the namespace count is 67, not 66, and the vacuity proof must be
re-stated to survive it.** Sixty-six namespace definitions declare
`schema_version=SECURE_OBJECT_SCHEMA_VERSION_V1`, but a sixty-seventh
(`_namespace_registry.py:1095`) declares `schema_version=BLOB_MANIFEST_SCHEMA_VERSION`.
The proof holds only because that constant is also `1`
(`_namespace_registry.py:40`) — a coincidence of value, not a shared authority.
The consequence is for the gate, not the argument: a gate written as "every
registered namespace equals 1" would pin a literal that a legitimate future
per-namespace bump breaks for the wrong reason, reddening on a correct change.
The gate must instead assert that each namespace's declared version is the
version its readers compare against — a relation, not a constant. The
`Envelope.schema_version` floor is confirmed as `Field(ge=1)`
(`envelope/_envelope.py:174`), so the below-current region is empty and `> 1` and
`!= 1` remain the same predicate today.

**Correction 2 — the equality form is already the majority shape, which
strengthens the case.** Beyond the two canonical sites this record cites,
equality is what newer persisted readers already do:
`blob_store/_blob_store.py:443`, `attachment.py:97`,
`master_key/_persisted_session.py:706`, `master_key/_login_throttle.py:115`,
`auth/_session_store.py:83`, `auth/_authenticator.py:1033`, and three further
envelope sites (`_envelope.py:469`, `:543`, `_secure_repository.py:274`). So the
twenty are not a competing convention with equal standing; they are a minority
residue of an older spelling, and the tightening moves them onto the shape the
rest of the substrate already uses. That was not visible from the inventory above
and is the strongest single argument for acting.

## Considered options

- **Leave the `>` form.** Correct today by the vacuity proof, and defensible as
  "no observable defect exists". Rejected: it leaves the post-bump tripwire
  disarmed, and the same edit costs materially more after the regime flip, when it
  must be argued against real filed data instead of an empty below-current region.
- **Tighten to `!=` inline at each of the twenty sites.** Minimal and
  behaviour-identical. Rejected as the whole answer: it leaves no shared symbol
  for a structural gate to bind, so the `>` form re-enters on the next author who
  copies a neighbouring site — which is how twenty instances accumulated.
- **Consolidate the twenty checks into one shared RAISING helper.** Tempting
  because every constant is literally the namespace definition's own
  `schema_version`. Rejected: it flattens the deliberate per-site error identity,
  translated message keys, and per-object diagnostics, and it silently re-routes
  the ordering-sensitive usage-ratio path through a different except clause.
- **Chosen — one shared non-raising predicate, each site keeping its own raise,
  plus a structural gate.** Derives the comparison from the namespace constant in
  one place, preserves every site's error type and context verbatim, is immune to
  the ordering hazard because it never raises, and gives the gate a single symbol
  to enforce.

## Constraints

- The change MUST be behaviour-identical at every current version, and its
  vacuity MUST be provable rather than asserted: the argument depends jointly on
  every namespace sitting at 1 and on the `ge=1` floor of the envelope field, so a
  gate must pin both facts rather than leave them as coincidence.
- The shared predicate MUST NOT raise. The usage-ratio except-clause ordering
  makes a raising helper an observable behaviour change at that one site even
  though the comparison itself is unchanged.
- Each site MUST keep its existing exception type, translated message key, and
  per-object context fields. This constraint is what defeated the naive
  consolidation and is not negotiable.
- Import hygiene: the predicate is consumed through the storage package's public
  facade, per `service-imports-via-top-level-reexports`; the per-tier archive and
  bundle constants stay intra-package.
- Honest limit: the obligation that an upgrader must re-stamp the inner envelope
  is only VACUOUSLY assertable while the upgrader registry is empty. It ships as a
  documented obligation on the registration surface plus a gate that becomes
  substantive on the first registered hop — not as a fabricated old-shape fixture,
  which `no-legacy-compatibility` forbids.
- This record does not depend on the regime flipping. It is correct and no-op
  under `PRE_RELEASE`, and correct and load-bearing under `RELEASED`.

## Implementation

Ruled `accepted` on the chosen option: one shared non-raising predicate, each site
keeping its own raise, plus a structural gate. The work below is carried by
`2026-07-25-code-dedup-sweep-plan`.

**The predicate.** One function lands in the storage substrate beside the existing
lineage policy, taking the stored inner version and the namespace's current
version and returning a boolean. It MUST NOT raise — the ordering-sensitive
`usage_ratios.py:88` site, whose raise sits inside a `try` whose
`except (ClassificationError, EnvelopeVersionError)` re-raises
`UsageRatioPersistenceError`, makes a raising helper an observable behaviour
change there even though the comparison is unchanged. It is consumed through the
storage package's public facade per `service-imports-via-top-level-reexports`.
Note that `ensure_schema_version_readable` stays deliberately absent from that
facade: it is the layer-one gate, and promoting it would advertise the wrong
contract to layer-two callers.

**The twenty sites.** Each replaces its inequality with a call to the predicate
and changes nothing else — same exception class, same translated message key,
same per-object context mapping, same logging. This is not negotiable and is what
defeated the naive consolidation: six profile sites raise `ModeloError` and
`BucketsError` descendants on a different error branch from `EnvelopeVersionError`,
each enrolled in the core error registry that drives envelope and exit-code
mapping, and each caught narrowly by exact type in tests. The per-object
diagnostics (`object_key`, `bucket_id`, `amendment_id`, observation and snapshot
labels) identify which row is unreadable and the layer-one gate cannot produce
them. Land the sweep in one atomic explicit-pathspec commit so no site is left
straddling the two shapes; the shared worktree makes a half-swept state worse
than either endpoint.

**Out of scope, unchanged.** The sealed-archive range gate
(`bucket_maintenance/_service.py:149` paired with `:157`) and the
encrypted-bundle envelope gate (`user_profile/_bundle_encryption.py:91` paired
with `:99`) already carry the two-sided shape this decision brings to the
secure-object inner layer, and `_bundle.py:121`/`:131` is the same correct
pattern. Layer one is untouched.

**Two gates.** First, a structural AST gate asserting that no persisted
inner-envelope read path compares `schema_version` with an inequality operator,
built in the shape the project already uses for the modelo-literal gate. It MUST
ship with an anti-tautology proof that plants a violation and proves the gate
catches it, and it MUST resolve import aliases rather than matching a name — this
audit's own critical finding is that two structural gates reported green against
violations they could not see, and `a5d21ced8a` has already established the
alias-aware pattern plus the planted-violation proof to copy. A gate landed here
without a failure proof would reproduce the exact defect this campaign's
highest-value finding identified.

Second, a lineage-gate addition pinning the facts the vacuity proof rests on. Per
Correction 1 above this is a relation, not a literal: assert that each registered
namespace's declared `schema_version` is the version its reader compares against,
and that the `Envelope.schema_version` field retains its `ge=1` floor. Record the
inner-re-stamp obligation against the upgrader registration surface so the first
registered hop inherits it explicitly.

**The honest limit stays honest.** The obligation that an upgrader must re-stamp
the inner envelope is only vacuously assertable while the upgrader registry is
empty. It ships as a documented obligation plus a gate that becomes substantive on
the first registered hop — never as a fabricated old-shape fixture, which
`no-legacy-compatibility` forbids. Under the mandated post-flip restorability test
it becomes directly executable.

No locale catalogue entry is added: every site keeps its existing message key,
because no new refusal reason is introduced — the refusal set is unchanged, only
its trigger boundary is corrected.

**Carried forward, not folded in.** The bucket-manifest gap recorded under
Consequences is a fourth persisted format with no version gate of any kind. It is
strictly stronger than this record's subject and it is NOT closed here. It is
carried as a named step on the plan so it acquires an owner rather than resting
in an ADR's out-of-scope note, which is where it would otherwise rot.

## Rationale

The knockout criterion is cost asymmetry across the regime flip, not present-day
risk. The vacuity proof is strong enough to rule out any live defect: with all 66
namespaces at 1 and a `ge=1` field floor, the twenty sites and the canonical
equality contract are the same predicate today, and no writer can produce a
divergent inner stamp. That makes tightening free right now — a zero-behaviour
edit under `PRE_RELEASE`. The same edit after the first bump lands under
`RELEASED` is a hard refusal newly applied to data a taxpayer has already filed,
which is exactly the class of change the durability decisions made deliberately
expensive. Doing it while it is free is the only cheap moment available.

The tightening also restores a specific safeguard rather than adding generic
strictness. Because the outer record is re-stamped to current unconditionally
while the inner stamp moves only under an upgrader's own hand, the inner equality
check is the ONLY place a half-written upgrader is detectable at read time. The
loose form disarms it. Under `no-silent-under-declaration` the resulting failure
mode is the one the project treats as most serious: a payload of ambiguous shape
reaching a tax calculation with no operator-visible signal.

The regime question resolves in favour of acting rather than against it. Reading
`no-legacy-compatibility` as "the issue is vacuous, so leave it" conflates a
refusal with handling; the rule mandates the former and forbids only the latter,
and `compatibility-lifecycle` already blesses installing dormant gates whose
released branch is proven by construction. This decision is that same shape
applied one layer inward.

## Consequences

- Good: the inner-envelope contract becomes uniform across all read paths and
  matches its own documented equality semantics; the half-written-upgrader
  tripwire is armed before the bump that needs it; the structural gate prevents
  the loose form from re-accumulating; and the facts the vacuity proof rests on
  become pinned invariants instead of a fortunate coincidence.
- Accepted cost: twenty read paths change shape for zero present-day behaviour
  difference, which reads as churn to a reviewer who has not followed the
  post-bump argument — the rationale above is the answer and should survive into
  the commit message. A shared predicate is one more substrate symbol to keep
  coherent.
- Neutral: the refusal set, message keys, and error types are unchanged, so no
  operator-facing surface moves and no locale work is required.
- Bad, and deliberately accepted: the inner-re-stamp obligation cannot be
  executably proven until a real hop exists, so between this change and the first
  bump it rests on the documented obligation plus the equality check itself. That
  is the strongest position `no-legacy-compatibility` permits without fabricating
  a shape nothing wrote.
- Out of scope, and a stronger gap than this record's subject: the bucket manifest
  is a fourth persisted format carrying a `schema_version` field
  (`storage/bucket/_manifest.py:91`), hardcoded to 2 at create
  (`application/user_profile/_profile_repository.py:330`), passed through unchanged
  on every save (`:478`), and read at `storage/bucket/_manifest_io.py:157` with NO
  version gate of any kind — a manifest written by a newer application is accepted
  silently. That needs its own tier decision under the durability framing and is
  not folded in here. The manifest read surface was not audited beyond confirming
  the absence of a gate on this path.

### Ruling, and a correction to the premise that this record governs landed work

Ruled `accepted` at HEAD `7058ef827f` on the chosen option. The vacuity proof was
re-derived independently rather than taken from the record above, and it holds,
subject to Correction 1 in Considerations.

**This record governs nothing that has shipped, and the belief that it does is
wrong on the dates.** The dedup commits carrying this record's feature tag —
`8bf229716e refactor(adapters): dedup storage/inbound clone clusters (Batch A G1)`
and its siblings through `e9a3c35abe` — landed on 2026-07-21. This ADR was
scaffolded on 2026-07-25 at 16:39 (`f8fa62ef11`), four days later. Those commits
are jscpd clone-cluster extraction from the duplication-evidence-repair campaign;
they share the `code-dedup-sweep` feature tag only because, as the companion audit
records, `vault add adr` has no `--topic` flag and there is exactly one ADR
filename slot per feature per date. They have no relation to this record's
subject.

The subject itself — the layer-two `>` to `!=` tightening — is entirely
unimplemented: all twenty sites carry the loose form at HEAD, enumerated in
Considerations. So there is no divergence between record and reality to
reconcile, and no shipped work to retro-govern. This ADR is a forward decision,
and the sequencing it asks for — land the tightening while it is provably a no-op,
rather than after the first bump makes it a refusal against filed taxpayer data —
is intact and unspent.

The feature-tag collision is worth naming as a durable hazard rather than an
incidental: a reader who sees dedup commits and an ADR under one tag will
reasonably infer the ADR ruled them. It did not. Future campaigns should allocate
a distinct feature tag per decision, or scaffold ADRs serially from the
coordinator.
